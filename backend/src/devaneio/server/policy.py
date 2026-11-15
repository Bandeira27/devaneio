"""Política da mesa: quem pode dar qual comando e quando o turno termina sozinho.

Só decide; não executa nada. O motor não conhece jogadores: tudo aqui vive acima de
``game``. Os conjuntos particionam exatamente ``game.COMMANDS`` (um teste confere), então
comando novo no jogo precisa de um papel antes de chegar a uma mesa.
"""

from __future__ import annotations

from typing import Literal

from devaneio.game import READ_ONLY, TableMeta
from devaneio.schema import GameState

Kind = Literal["read", "join", "action", "host"]

# `marcos` lista também os marcos pendentes e seus requisitos: spoiler da trama. O jogador
# vê os marcos que já começaram pelo `olhar` e pela CampaignView.
# `log` lista todos os eventos, inclusive os sobre NPC escondido: o jogador lê o log
# filtrado por `GET .../events`.
HOST_ONLY = frozenset({"descansar", "fim", "ferir", "curar", "marco", "marcos", "log"})
PLAYER_READ = frozenset(READ_ONLY) - {"marcos", "log"}
JOIN = frozenset({"entrar"})
# Gastam a ação principal do personagem no turno. `ir` move o grupo todo, e `atacar`
# aceita o personagem de outro jogador como alvo: ficam como no motor (decisão do dono).
ACTIONS = frozenset({"testar", "atacar", "ir"})


def classify(name: str) -> Kind | None:
    """Papel do comando; ``None`` se o jogo não o conhece (``execute`` dá a mensagem)."""
    if name in PLAYER_READ:
        return "read"
    if name in JOIN:
        return "join"
    if name in ACTIONS:
        return "action"
    if name in HOST_ONLY:
        return "host"
    return None


def eligible(table: TableMeta, state: GameState) -> list[str]:
    """Personagens que ainda contam para o fim automático do turno: ligados a um jogador e
    de pé (hp 0 fica fora de combate e não segura o turno)."""
    return [
        character_id
        for player in table.players.values()
        for character_id in player.character_ids
        if character_id in state.characters and state.characters[character_id].hp > 0
    ]


def everyone_acted(table: TableMeta, state: GameState) -> bool:
    """Todos os elegíveis já fizeram a ação principal neste turno (e há ao menos um)."""
    waiting = eligible(table, state)
    return bool(waiting) and all(table.acted.get(c) == state.turn for c in waiting)
