"""Do evento mecânico à prosa.

Função pura: mesmo evento, mesmo índice, mesma semente → mesmo texto. Não consome ``rng_draws``: a
variedade vem de um Rng próprio semeado por (semente da partida, índice do evento), então narrar não
altera nada no jogo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from devaneio.rng import Rng
from devaneio.rules import RuleSystem
from devaneio.schema import Campaign, Event, GameState, Location

from .grammar import Grammar, GrammarError
from .pack import NarrationPack

_SALT = 0x9E3779B97F4A7C15


@dataclass
class Narrator:
    """Transforma os eventos do log em prosa a partir de um pacote de narração."""

    campaign: Campaign
    rules: RuleSystem
    pack: NarrationPack
    grammar: Grammar = field(init=False)

    def __post_init__(self) -> None:
        self.grammar = Grammar(self.pack.rules)

    def narrate(self, event: Event, index: int, state: GameState) -> str:
        """A prosa do evento na posição ``index`` do log.

        O índice entra no sorteio das alternativas: mesmo evento, índice e semente dão o mesmo texto.
        Sem regra, devolve o texto mecânico do evento.
        """
        variant, variables = self._prepare(event, state)
        key = next(
            (k for k in (f"{event.kind}.{variant}", event.kind) if k in self.grammar.rules),
            None,
        )
        if key is None:
            return event.text
        rng = Rng(state.rng_seed ^ ((index + 1) * _SALT))
        try:
            return " ".join(self.grammar.expand(key, variables, rng).split())
        except GrammarError:  # pacote que a validação não pegou: o jogo segue com o texto mecânico
            return event.text

    def narrate_all(self, state: GameState) -> list[str]:
        """A prosa de todos os eventos do log, na ordem."""
        return [self.narrate(e, i, state) for i, e in enumerate(state.events)]

    def rule_key(self, event: Event, state: GameState) -> str | None:
        """Qual regra narraria este evento (útil em testes e depuração)."""
        variant, _ = self._prepare(event, state)
        return next(
            (k for k in (f"{event.kind}.{variant}", event.kind) if k in self.grammar.rules), None
        )

    # --- contexto por tipo de evento -------------------------------------------

    def _prepare(self, event: Event, state: GameState) -> tuple[str, dict[str, str]]:
        d = event.data
        kind = event.kind
        if kind == "check":
            return str(d.get("outcome", "")), {
                "ator": self._name(state, d.get("actor_kind"), d.get("actor_id")),
                "habilidade": self._skill(d.get("skill_id")),
                "dificuldade": self._difficulty(d.get("difficulty_id")),
                "total": str(d.get("total", "")),
                "margem": str(d.get("margin", "")),
                "desfecho": str(d.get("outcome", "")),
            }
        if kind == "damage":
            attacker = (
                self._name(state, d.get("attacker_kind"), d.get("attacker_id"))
                if d.get("attacker_id")
                else ""
            )
            weapon = self._weapon(d.get("weapon_id")) if d.get("weapon_id") else ""
            variant = ("golpe" if attacker else "fonte") + (
                "_queda" if d.get("incapacitated") else ""
            )
            return variant, {
                "atacante": attacker,
                "alvo": self._name(state, d.get("target_kind"), d.get("target_id")),
                "arma": weapon,
                "fonte": weapon or str(d.get("source", "")),
                "dano": str(d.get("amount", "")),
                "hp": str(d.get("hp_after", "")),
                "hp_max": str(self._max_hp(state, d.get("target_kind"), d.get("target_id"))),
            }
        if kind == "heal":
            return "", {
                "alvo": self._name(state, d.get("target_kind"), d.get("target_id")),
                "fonte": str(d.get("source", "")),
                "cura": str(d.get("amount", "")),
                "hp": str(d.get("hp_after", "")),
                "hp_max": str(self._max_hp(state, d.get("target_kind"), d.get("target_id"))),
            }
        if kind == "rest":
            healed = d.get("healed", {})
            parts = [
                f"{self._name(state, 'character', cid)} (+{info.get('amount', 0)})"
                for cid, info in healed.items()
            ]
            return "", {"curados": ", ".join(parts)}
        if kind == "move":
            dest = self._location(d.get("to_location_id"))
            return "", {
                "origem": self._location(d.get("from_location_id")).name,
                "destino": dest.name,
                "descricao": dest.description,
            }
        if kind == "character_joined":
            return "", {
                "ator": self._name(state, "character", d.get("character_id")),
                "hp": str(d.get("max_hp", "")),
            }
        if kind == "turn_end":
            return "", {"turno": str(event.turn)}
        if kind == "director":
            level = float(d.get("tension", 0.0))
            variant = "calmo" if level < 0.25 else "tenso" if level < 0.6 else "critico"
            return variant, {
                "tensao": f"{level:.2f}",
                "local": self._location(state.current_location_id).name,
            }
        if kind in ("beat_activated", "beat_done", "beat_failed"):
            beat = next((b for b in self.campaign.beats if b.id == d.get("beat_id")), None)
            return "", {
                "marco": beat.title if beat else str(d.get("beat_id", "")),
                "descricao": beat.description if beat else "",
            }
        if kind == "reveal":
            fact = next((f for f in self.campaign.facts if f.id == d.get("fact_id")), None)
            return "", {"fato": fact.text if fact else ""}
        return "", {}

    # --- buscas com fallback para o id -----------------------------------------

    def _name(self, state: GameState, kind: str | None, who_id: str | None) -> str:
        if who_id is None:
            return ""
        if kind == "character":
            char = state.characters.get(who_id)
            return char.name if char else who_id
        npc = next((n for n in self.campaign.npcs if n.id == who_id), None)
        return npc.name if npc else who_id

    def _max_hp(self, state: GameState, kind: str | None, who_id: str | None) -> int | str:
        if kind == "character" and who_id in state.characters:
            return state.characters[who_id].max_hp
        if kind == "npc" and who_id in state.npcs:
            return state.npcs[who_id].max_hp
        return ""

    def _skill(self, skill_id: str | None) -> str:
        skill = next((s for s in self.rules.skills if s.id == skill_id), None)
        return skill.name if skill else str(skill_id)

    def _difficulty(self, difficulty_id: str | None) -> str:
        diff = next((x for x in self.rules.difficulties if x.id == difficulty_id), None)
        return diff.name if diff else str(difficulty_id)

    def _weapon(self, weapon_id: str | None) -> str:
        weapon = next((w for w in self.rules.weapons if w.id == weapon_id), None)
        return weapon.name if weapon else str(weapon_id)

    def _location(self, location_id: str | None) -> Location:
        loc = next((c for c in self.campaign.locations if c.id == location_id), None)
        if loc is None:
            return Location(id=location_id or "x", name=str(location_id), description="")
        return loc
