"""Comandos de consulta: mostram o estado sem alterá-lo (valem com a partida encerrada)."""

from __future__ import annotations

from devaneio.engine import GameStatus, game_status, npc_ids_at
from devaneio.schema import BeatStatus, Character, GameState

from ..session import Session
from .actors import resolve_actor
from .errors import CommandError
from .help import HELP
from .labels import BEAT_LABELS, STATUS_LABELS


def cmd_help(session: Session, _actor: str | None, _args: list[str]) -> tuple[GameState, str]:
    """`ajuda`: a lista de comandos."""
    return session.state, HELP


def cmd_look(session: Session, _actor: str | None, _args: list[str]) -> tuple[GameState, str]:
    """`olhar`: onde o grupo está, saídas, quem está aqui e o que o grupo sabe."""
    state, campaign = session.state, session.campaign
    here = next(loc for loc in campaign.locations if loc.id == state.current_location_id)
    names = {loc.id: loc.name for loc in campaign.locations}
    npc_names = {n.id: n.name for n in campaign.npcs}

    lines = [f"Turno {state.turn} — {here.name} ({here.id})"]
    status = game_status(state)
    if status is not GameStatus.ACTIVE:
        lines.append(f"Partida encerrada — {STATUS_LABELS[status]}.")
    if here.description:
        lines.append(here.description)
    exits = ", ".join(f"{names[c]} ({c})" for c in here.connections) or "nenhuma"
    lines.append(f"Saídas: {exits}")

    hostile_below = session.rules.dispositions.hostile_below
    present = [
        f"{npc_names[npc_id]} ({npc_id}) hp {npc.hp}/{npc.max_hp}"
        + (
            ", fora de combate"
            if not npc.alive
            else ", hostil"
            if npc.disposition < hostile_below
            else ""
        )
        for npc_id, npc in state.npcs.items()
        if npc_id in npc_ids_at(state, here.id)
    ]
    lines.append("Aqui: " + (", ".join(present) if present else "ninguém"))
    titles = {b.id: b.title for b in campaign.beats}
    active = [titles[b] for b, st in state.beats.items() if st is BeatStatus.ACTIVE]
    if active:
        lines.append("Marcos ativos: " + ", ".join(active))
    known = [f.text for f in campaign.facts if f.id in state.revealed_facts]
    if known:
        lines.append("Vocês sabem: " + " ".join(known))

    if state.characters:
        party = ", ".join(_char_line(c) for c in state.characters.values())
    else:
        party = 'ninguém ainda (use: entrar <id> "<nome>" [FOR=3 ...])'
    lines.append("Grupo: " + party)
    return state, "\n".join(lines)


def cmd_sheet(session: Session, actor: str | None, args: list[str]) -> tuple[GameState, str]:
    """`ficha [id]`: atributos, hp e inventário de um personagem."""
    if len(args) > 1:
        raise CommandError("uso: ficha [id]")
    character = resolve_actor(session, args[0] if args else actor)
    attrs = ", ".join(f"{k} {v}" for k, v in character.attributes.items())
    inventory = ", ".join(character.inventory) or "vazio"
    return session.state, (
        f"{character.name} ({character.id})\n"
        f"hp {character.hp}/{character.max_hp}\n"
        f"{attrs}\n"
        f"Inventário: {inventory}"
    )


def cmd_log(session: Session, _actor: str | None, args: list[str]) -> tuple[GameState, str]:
    """`log [n]`: os últimos eventos (padrão 10)."""
    count = 10
    if args:
        if len(args) != 1 or not args[0].isdigit():
            raise CommandError("uso: log [n]")
        count = int(args[0])
    events = session.state.events[-count:] if count else []
    if not events:
        return session.state, "Nenhum evento ainda."
    return session.state, "\n".join(f"[t{e.turn}] {e.text}" for e in events)


def cmd_beats(session: Session, _actor: str | None, _args: list[str]) -> tuple[GameState, str]:
    """`marcos`: os marcos da trama e seus estados."""
    lines = []
    for beat in session.campaign.beats:
        status = session.state.beats[beat.id]
        requires = f" (exige: {', '.join(beat.requires)})" if beat.requires else ""
        lines.append(f"[{BEAT_LABELS[status]}] {beat.title} ({beat.id}){requires}")
    return session.state, "\n".join(lines)


def cmd_facts(session: Session, _actor: str | None, _args: list[str]) -> tuple[GameState, str]:
    """`fatos`: os fatos da campanha, revelados e ocultos."""
    lines = []
    for fact in session.campaign.facts:
        label = "revelado" if fact.id in session.state.revealed_facts else "oculto"
        about = f" sobre {fact.about}" if fact.about else ""
        lines.append(f"[{label}] {fact.text} ({fact.id}){about}")
    return session.state, "\n".join(lines) or "Nenhum fato na campanha."


def _char_line(c: Character) -> str:
    attrs = " ".join(f"{k} {v}" for k, v in c.attributes.items())
    down = ", fora de combate" if c.hp == 0 else ""
    return f"{c.name} ({c.id}) hp {c.hp}/{c.max_hp}{down} | {attrs}"
