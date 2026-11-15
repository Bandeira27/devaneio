"""Busca de combatentes (personagem ou NPC) com nome, atributos e hp."""

from __future__ import annotations

from devaneio.schema import Campaign, GameState

from .errors import EngineError

KINDS = ("character", "npc")


def npc_locations(state: GameState, *who: tuple[str, str]) -> dict[str, str]:
    """Onde estavam, agora, os NPCs entre ``(tipo, id)``. Os eventos gravam isso em
    ``data["npc_locations"]``: quem filtra o log (o jogador não vê NPC de outro local) não
    depende de o NPC continuar onde estava, o que vale se um dia NPCs puderem andar."""
    found: dict[str, str] = {}
    for kind, who_id in who:
        npc = state.npcs.get(who_id) if kind == "npc" else None
        if npc is not None and npc.location_id is not None:
            found[who_id] = npc.location_id
    return found


def npc_ids_at(state: GameState, location_id: str) -> frozenset[str]:
    """Ids dos NPCs que estão num local. É o critério de "quem o grupo vê aqui": o ``olhar``, as
    visões do jogador na mesa e o filtro do log usam esta função, então mudar o critério
    (NPC escondido por um efeito, por exemplo) é mudar um lugar só."""
    return frozenset(k for k, v in state.npcs.items() if v.location_id == location_id)


def combatant(
    state: GameState, campaign: Campaign, kind: str, who_id: str
) -> tuple[str, dict[str, int], int]:
    """(nome, atributos, hp). Nome de NPC vem da campanha; o resto, do estado."""
    if kind == "character":
        char = state.characters.get(who_id)
        if char is None:
            raise EngineError(f"personagem '{who_id}' não está no estado")
        return char.name, char.attributes, char.hp
    if kind == "npc":
        npc = state.npcs.get(who_id)
        if npc is None:
            raise EngineError(f"npc '{who_id}' não está no estado")
        static = next((n for n in campaign.npcs if n.id == who_id), None)
        if static is None:
            raise EngineError(f"npc '{who_id}' não existe na campanha")
        return static.name, npc.attributes, npc.hp
    raise EngineError(f"tipo de alvo desconhecido: {kind!r} (use {KINDS})")
