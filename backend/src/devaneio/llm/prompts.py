"""Prompts e contexto para o LLM no papel de mestre que PROPÕE ações."""

from __future__ import annotations

import json
from typing import Any

from devaneio.rules import RuleSystem
from devaneio.schema import Campaign, GameState

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
- Em falas de NPC, use só o que consta em "descricao" e no contexto; não invente fatos novos.
- Não revele "segredos" de NPCs a menos que o jogador os descubra por uma ação bem-sucedida.

Ações permitidas:
  {{"kind": "check", "skill": <id de habilidades>, "difficulty": <id de dificuldades>, "modifier": <id de modificadores ou null>}}
  {{"kind": "attack", "weapon": <id de armas_do_personagem>, "target": <id de alvos>, "modifier": <id ou null>}}
  {{"kind": "move", "to": <id de saidas>}}
  {{"kind": "rest"}}

Formato da resposta (exemplo; use os ids do catálogo da partida):
{json.dumps(EXAMPLE_PROPOSAL, ensure_ascii=False)}
"""


def build_context(
    campaign: Campaign, rules: RuleSystem, state: GameState, actor_id: str
) -> dict[str, Any]:
    here = next(loc for loc in campaign.locations if loc.id == state.current_location_id)
    names = {loc.id: loc.name for loc in campaign.locations}
    static = {n.id: n for n in campaign.npcs}
    actor = state.characters[actor_id]

    npcs_here = []
    for npc_id, npc in state.npcs.items():
        if npc.location_id != here.id or npc_id not in static:
            continue
        info = static[npc_id]
        npcs_here.append(
            {
                "id": npc_id,
                "nome": info.name,
                "descricao": info.description,
                "segredos": info.secrets,
                "hp": f"{npc.hp}/{npc.max_hp}",
                "de_pe": npc.alive and npc.hp > 0,
                "hostil": npc.disposition < rules.dispositions.hostile_below,
            }
        )

    weapon_ids = {w.id for w in rules.weapons}
    weapons = [i for i in actor.inventory if i in weapon_ids]
    if rules.combat.default_weapon and rules.combat.default_weapon not in weapons:
        weapons.append(rules.combat.default_weapon)

    targets = [c for c in state.characters if c != actor_id] + [
        n["id"] for n in npcs_here if n["de_pe"]
    ]
    return {
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
        "marcos_ativos": [
            {"titulo": b.title, "descricao": b.description}
            for b in campaign.beats
            if state.beats.get(b.id) is not None and state.beats[b.id].value == "active"
        ],
        "eventos_recentes": [e.text for e in state.events[-5:]],
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


def build_messages(
    campaign: Campaign, rules: RuleSystem, state: GameState, actor_id: str, player_text: str
) -> list[dict[str, str]]:
    context = json.dumps(build_context(campaign, rules, state, actor_id), ensure_ascii=False)
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
