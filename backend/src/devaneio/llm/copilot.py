"""Copiloto do anfitrião: um LLM que assessora quem narra a mesa e NÃO altera nada.

Recebe a campanha inteira, segredos e fatos ocultos inclusive: a resposta volta só ao anfitrião,
que configurou o LLM e já vê tudo pela API. Por isso este módulo nunca deve ser usado para texto
que chegue aos jogadores (para isso existe ``prompts.build_context`` com o recorte público).
O copiloto responde, sugere e rascunha; quem aplica algo é o anfitrião, pelos comandos de sempre.
"""

from __future__ import annotations

import json
from typing import Any

from devaneio.rules import RuleSystem
from devaneio.schema import Campaign, GameState, Npc, NpcState

from .client import ChatClient
from .errors import LlmError
from .text import clean_multiline

RECENT_EVENTS = 15
MAX_ANSWER_CHARS = 2000
COPILOT_TEMPERATURE = 0.5
# Teto do contexto serializado (cerca de 15 mil tokens): campanha grande demais estouraria a janela do
# modelo e o pedido falharia por um motivo obscuro. Passando do teto o contexto encolhe em etapas.
MAX_CONTEXT_CHARS = 60_000
REDUCED_EVENTS = 5
TEXT_CUT = 200  # tamanho máximo de cada texto livre na última etapa de encolhimento


class CopilotContextTooLarge(ValueError):
    """Mesmo encolhido, o contexto da campanha passa de ``MAX_CONTEXT_CHARS``."""


COPILOT_SYSTEM = """\
Você é o copiloto do anfitrião (mestre) de uma mesa de RPG, em português do Brasil. Só o anfitrião lê
a sua resposta. Você recebe a campanha INTEIRA, inclusive segredos, notas privadas, fatos ainda não
revelados, marcos pendentes e as condições que os fazem avançar.

O que fazer: responder a pergunta do anfitrião, sugerir o próximo marco ou uma cena, rascunhar falas de
NPC, e avisar quando algo que ele pretende dizer ou fazer revelaria um segredo antes da hora.

Regras:
- Você NÃO altera o jogo. Nunca diga que fez, aplicou, revelou ou mudou algo: você só sugere. O anfitrião
  aplica pelos comandos dele.
- Condições de marcos e fatos ("ativa_quando", "conclui_quando", "revela_quando"): TODAS as de uma lista
  precisam valer ao mesmo tempo (E, nunca "ou"). Lista vazia em "conclui_quando" ou "revela_quando" quer
  dizer que só o anfitrião decide. Tipos: at_location = o grupo está nesse local; npc_down = esse NPC caiu;
  beat_done = esse marco foi concluído; turn_at_least = chegou a esse turno; check_passed = algum
  personagem passou num teste dessa habilidade.
- Use só o que está no contexto. Não invente fatos, NPCs, locais nem resultados de testes.
- Quando citar um segredo, marque-o como segredo ("[segredo]") para o anfitrião não repetir por engano
  aos jogadores.
- Responda curto: até uns 8 parágrafos curtos ou itens. Sem JSON.
"""


def build_copilot_context(
    campaign: Campaign, rules: RuleSystem, state: GameState
) -> dict[str, Any]:
    """A campanha e o estado inteiros, num formato compacto para o prompt. Sem ``rng_seed`` nem
    ``rng_draws`` (de nada servem a um assistente) e sem filtro de visibilidade."""
    names = {
        **{loc.id: loc.name for loc in campaign.locations},
        **{n.id: n.name for n in campaign.npcs},
        **{f.id: f.name for f in campaign.factions},
        **{b.id: b.title for b in campaign.beats},
    }
    here = next((loc for loc in campaign.locations if loc.id == state.current_location_id), None)
    npc_states = state.npcs
    return {
        "turno": state.turn,
        "local_atual": here.name if here else state.current_location_id,
        "grupo": [
            {"id": c.id, "nome": c.name, "hp": f"{c.hp}/{c.max_hp}", "inventario": c.inventory}
            for c in state.characters.values()
        ],
        "campanha": {"titulo": campaign.title, "premissa": campaign.premise},
        "locais": [
            {
                "id": loc.id,
                "nome": loc.name,
                "descricao": loc.description,
                "saidas": loc.connections,
                "notas_privadas": loc.private_notes,
            }
            for loc in campaign.locations
        ],
        "faccoes": [
            {
                "id": f.id,
                "nome": f.name,
                "descricao": f.description,
                "objetivos": f.goals,
                "notas_privadas": f.private_notes,
            }
            for f in campaign.factions
        ],
        "npcs": [_npc_entry(n, npc_states.get(n.id), rules) for n in campaign.npcs],
        "marcos": [
            {
                "id": b.id,
                "titulo": b.title,
                "descricao": b.description,
                "estado": state.beats[b.id].value if b.id in state.beats else None,
                "requer": b.requires,
                "ativa_quando": [c.model_dump(mode="json") for c in b.activate_when],
                "conclui_quando": [c.model_dump(mode="json") for c in b.complete_when],
                "notas_privadas": b.private_notes,
            }
            for b in campaign.beats
        ],
        "fatos": [
            {
                "id": f.id,
                "texto": f.text,
                "sobre": names.get(f.about or ""),
                "revelado": f.id in state.revealed_facts,
                "revelado_no_turno": state.revealed_facts.get(f.id),
                "revela_quando": [c.model_dump(mode="json") for c in f.reveal_when],
            }
            for f in campaign.facts
        ],
        "eventos_recentes": [e.text for e in state.events[-RECENT_EVENTS:]],
    }


def _npc_entry(npc: Npc, st: NpcState | None, rules: RuleSystem) -> dict[str, Any]:
    """Sem estado (NPC novo numa campanha editada depois da partida), os campos vivos são ``None``
    em vez de parecerem um NPC caído: ausência de dado não vira afirmação."""
    return {
        "id": npc.id,
        "nome": npc.name,
        "descricao": npc.description,
        "faccao": npc.faction_id,
        "local": st.location_id if st else npc.location_id,
        "de_pe": None if st is None else st.alive and st.hp > 0,
        "hp": None if st is None else f"{st.hp}/{st.max_hp}",
        "hostil": None if st is None else st.disposition < rules.dispositions.hostile_below,
        "notas_privadas": npc.private_notes,
    }


def _dump(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=False, separators=(",", ":"))


def _cut(value: Any) -> Any:
    """Corta cada texto livre acima de ``TEXT_CUT`` (ids e nomes são curtos e ficam como estão)."""
    if isinstance(value, str):
        return value if len(value) <= TEXT_CUT else value[: TEXT_CUT - 1] + "…"
    if isinstance(value, list):
        return [_cut(v) for v in value]
    if isinstance(value, dict):
        return {k: _cut(v) for k, v in value.items()}
    return value


def fit_context(context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """O contexto dentro do teto, e o JSON dele. Etapas, da que menos perde à que mais: menos
    eventos recentes, nenhum evento, textos livres cortados. Quando algo é cortado o próprio contexto
    traz um ``aviso`` para o modelo não tratar o que falta como inexistente."""
    text = _dump(context)
    if len(text) <= MAX_CONTEXT_CHARS:
        return context, text
    reduced = dict(context)
    notes: list[str] = []
    for keep in (REDUCED_EVENTS, 0):
        reduced["eventos_recentes"] = context["eventos_recentes"][-keep:] if keep else []
        notes = [f"só os {keep} eventos mais recentes" if keep else "sem eventos recentes"]
        if len(_dump(reduced)) <= MAX_CONTEXT_CHARS:
            break
    else:
        reduced = _cut(reduced)
        notes.append(f"textos longos cortados em {TEXT_CUT} caracteres")
    reduced["aviso"] = "Contexto reduzido por tamanho: " + "; ".join(notes) + "."
    text = _dump(reduced)
    if len(text) > MAX_CONTEXT_CHARS:
        raise CopilotContextTooLarge(
            f"o contexto da campanha tem {len(text)} caracteres; o teto do copiloto é {MAX_CONTEXT_CHARS}"
        )
    return reduced, text


def build_copilot_messages(
    campaign: Campaign, rules: RuleSystem, state: GameState, question: str
) -> list[dict[str, str]]:
    _, context = fit_context(build_copilot_context(campaign, rules, state))
    return [
        {"role": "system", "content": COPILOT_SYSTEM},
        {"role": "user", "content": f"CONTEXTO\n{context}\n\nPERGUNTA DO ANFITRIÃO\n{question}"},
    ]


def ask_copilot(
    client: ChatClient, campaign: Campaign, rules: RuleSystem, state: GameState, question: str
) -> str:
    """Uma chamada (sem as tentativas do proposer: custo) e a resposta limpa para a tela do
    anfitrião. ``LlmError`` se o servidor falhar ou devolver só lixo."""
    messages = build_copilot_messages(campaign, rules, state, question)
    raw = client.complete(messages, json_mode=False, temperature=COPILOT_TEMPERATURE)
    answer = clean_multiline(raw, MAX_ANSWER_CHARS)
    if not answer:
        raise LlmError("o copiloto devolveu uma resposta vazia")
    return answer
