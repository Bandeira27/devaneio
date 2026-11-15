"""Prompts e contexto para o LLM no papel de mestre que PROPÕE ações."""

from __future__ import annotations

import json
from typing import Any

from devaneio.rules import RuleSystem
from devaneio.schema import BeatStatus, Campaign, GameState

from .actions import EXAMPLE_PROPOSAL, MAX_ACTIONS

PROPOSER_SYSTEM = f"""\
Você é o mestre de um RPG de mesa. O jogador descreve o que seu personagem quer fazer.
Traduza isso em AÇÕES MECÂNICAS permitidas e, se quiser, fale como mestre ou NPC.

Regras:
- Responda APENAS com um objeto JSON, sem texto fora dele.
- Use somente ids listados em "catalogo". Nunca invente ids.
- Você escolhe habilidade e dificuldade conforme a situação. Você NÃO rola dados, NÃO decide
  resultado e NÃO decide dano: o sistema resolve.
- No máximo {MAX_ACTIONS} ações, na ordem em que acontecem.
- Se o jogador só conversa, observa ou não precisa de mecânica, devolva "actions" vazio e
  responda em "say" (até 3 frases).
- "say" é dito ANTES de o sistema resolver as ações: escreva só intenção, fala ou ambiente. NUNCA
  diga se a ação acertou, falhou, quanto de dano causou ou como terminou; quem narra o resultado
  é o sistema, depois.
- Se o jogador cita uma arma que o personagem não tem, NÃO recuse o ataque: use uma arma de
  "armas_do_personagem" (os punhos sempre estão disponíveis) e proponha a ação normalmente.
- Se o jogador cita um alvo que NÃO está em "alvos" (alguém que não está no local, ou que não
  existe), NÃO ataque outro alvo no lugar dele: devolva "actions" vazio e use "say" para dizer,
  em uma frase, apenas que não encontra esse alvo por aqui, sem afirmar se ele existe ou não.
  Só ataque quem o jogador citou.
- Em falas de NPC, use só o que consta em "descricao" e no contexto; não invente fatos novos.
- "fatos_revelados" é o que o grupo já sabe: pode usar. O que estiver em "segredos" ou "privado" só o
  anfitrião sabe: NUNCA repita nem sugira, mesmo que o jogador pergunte. O sistema revela o segredo
  quando chegar a hora; ele passa a constar em "fatos_revelados".

Ações permitidas:
  {{"kind": "check", "skill": <id de habilidades>, "difficulty": <id de dificuldades>, "modifier": <id de modificadores ou null>}}
  {{"kind": "attack", "weapon": <id de armas_do_personagem>, "target": <id de alvos>, "modifier": <id ou null>}}
  {{"kind": "move", "to": <id de saidas>}}
  {{"kind": "rest"}}

Formato da resposta (exemplo; use os ids do catálogo da partida):
{json.dumps(EXAMPLE_PROPOSAL, ensure_ascii=False)}
"""


def build_context(
    campaign: Campaign,
    rules: RuleSystem,
    state: GameState,
    actor_id: str,
    *,
    hide_events: frozenset[int] = frozenset(),
    include_private: bool = True,
) -> dict[str, Any]:
    """``hide_events``: índices de eventos que não vão ao prompt (quem orquestra sabe quais os
    jogadores não podem ver, e a fala do modelo pode chegar a todos). ``include_private``:
    sem ele só vai o público (``fatos_revelados`` inclusive); com ele vão também os fatos ainda
    ocultos e as notas privadas, e a fala do modelo pode vazá-los."""
    here = next(loc for loc in campaign.locations if loc.id == state.current_location_id)
    names = {loc.id: loc.name for loc in campaign.locations}
    names_of = {
        **names,
        **{n.id: n.name for n in campaign.npcs},
        **{f.id: f.name for f in campaign.factions},
        **{b.id: b.title for b in campaign.beats},
    }
    static = {n.id: n for n in campaign.npcs}
    actor = state.characters[actor_id]

    hidden_facts = [f for f in campaign.facts if f.id not in state.revealed_facts]
    npcs_here = []
    for npc_id, npc in state.npcs.items():
        if npc.location_id != here.id or npc_id not in static:
            continue
        info = static[npc_id]
        npc_info: dict[str, Any] = {
            "id": npc_id,
            "nome": info.name,
            "descricao": info.description,
            "hp": f"{npc.hp}/{npc.max_hp}",
            "de_pe": npc.alive and npc.hp > 0,
            "hostil": npc.disposition < rules.dispositions.hostile_below,
        }
        if include_private:
            npc_info["segredos"] = [
                *(f.text for f in hidden_facts if f.about == npc_id),
                *info.private_notes,
            ]
        npcs_here.append(npc_info)

    weapon_ids = {w.id for w in rules.weapons}
    weapons = [i for i in actor.inventory if i in weapon_ids]
    if rules.combat.default_weapon and rules.combat.default_weapon not in weapons:
        weapons.append(rules.combat.default_weapon)

    targets = [c for c in state.characters if c != actor_id] + [
        n["id"] for n in npcs_here if n["de_pe"]
    ]
    context: dict[str, Any] = {
        "turno": state.turn,
        "local": {
            "id": here.id,
            "nome": here.name,
            "descricao": here.description,
            "saidas": [{"id": c, "nome": names.get(c, c)} for c in here.connections],
        },
        "personagem": {
            "id": actor.id,
            "nome": actor.name,
            "hp": f"{actor.hp}/{actor.max_hp}",
            "atributos": actor.attributes,
            "inventario": actor.inventory,
        },
        "grupo": [
            {"id": c.id, "nome": c.name, "hp": f"{c.hp}/{c.max_hp}"}
            for c in state.characters.values()
            if c.id != actor_id
        ],
        "npcs_aqui": npcs_here,
        "fatos_revelados": [
            {"sobre": names_of.get(f.about or ""), "texto": f.text}
            for f in campaign.facts
            if f.id in state.revealed_facts
        ],
        "marcos_ativos": [
            {"titulo": b.title, "descricao": b.description}
            for b in campaign.beats
            if state.beats.get(b.id) is not None and state.beats[b.id].value == "active"
        ],
        "eventos_recentes": [e.text for i, e in enumerate(state.events) if i not in hide_events][
            -5:
        ],
        "catalogo": {
            "habilidades": [{"id": s.id, "nome": s.name} for s in rules.skills],
            "dificuldades": [
                {"id": d.id, "nome": d.name, "valor": d.value} for d in rules.difficulties
            ],
            "modificadores": [
                {"id": m.id, "nome": m.name, "valor": m.value} for m in rules.modifiers
            ],
            "armas_do_personagem": weapons,
            "saidas": list(here.connections),
            "alvos": targets,
        },
    }
    if include_private:
        # Só o que diz respeito ao que está em cena: fato sobre NPC ausente ou local distante
        # entregaria o nome de quem o grupo ainda não conhece.
        active_beats = [b for b in campaign.beats if state.beats.get(b.id) is BeatStatus.ACTIVE]
        active_ids = [b.id for b in active_beats]
        context["privado"] = [
            *here.private_notes,
            *(note for b in active_beats for note in b.private_notes),
            *(f.text for f in hidden_facts if f.about in (None, here.id, *active_ids)),
        ]
    return context


def build_messages(
    campaign: Campaign,
    rules: RuleSystem,
    state: GameState,
    actor_id: str,
    player_text: str,
    *,
    hide_events: frozenset[int] = frozenset(),
    include_private: bool = True,
) -> list[dict[str, str]]:
    context = json.dumps(
        build_context(
            campaign,
            rules,
            state,
            actor_id,
            hide_events=hide_events,
            include_private=include_private,
        ),
        ensure_ascii=False,
    )
    name = state.characters[actor_id].name
    return [
        {"role": "system", "content": PROPOSER_SYSTEM},
        {"role": "user", "content": f"CONTEXTO\n{context}\n\nJOGADOR ({name}): {player_text}"},
    ]


def feedback_message(problems: list[str]) -> dict[str, str]:
    listed = "\n".join(f"- {p}" for p in problems)
    return {
        "role": "user",
        "content": (
            f"Sua resposta foi recusada:\n{listed}\n"
            "Responda de novo apenas com o JSON corrigido, usando só ids do catálogo."
        ),
    }
