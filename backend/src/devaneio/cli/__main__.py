"""``python -m devaneio.cli nova <campanha.json> <partida.json> [--seed N]``
``python -m devaneio.cli jogar <partida.json>``"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from devaneio.schema import CampaignIntegrityError

from .commands import CommandError, execute
from .output import format_output, status_banner
from .session import CliError, load_game, new_game, save_game

QUIT = ("sair", "quit", "exit")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="devaneio", description="Devaneio: mesa de RPG.")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("nova", help="cria uma partida a partir de uma campanha")
    new.add_argument("campanha", type=Path, help="arquivo JSON da campanha")
    new.add_argument("partida", type=Path, help="arquivo JSON da partida a criar")
    new.add_argument("--seed", type=int, default=None, help="semente do RNG (aleatória se omitida)")

    play = sub.add_parser("jogar", help="abre uma partida salva")
    play.add_argument("partida", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "nova":
            session = new_game(args.campanha, args.partida, args.seed)
            print(
                f"Partida criada: {session.campaign.title} (seed {session.state.rng_seed})\n"
                f"Salva em {session.save_path}\n"
                f"Para jogar: python -m devaneio.cli jogar {args.partida}"
            )
            return 0
        return _play(load_game(args.partida))
    except FileNotFoundError as exc:
        print(f"erro: arquivo não encontrado: {exc.filename}", file=sys.stderr)
    except (ValidationError, CampaignIntegrityError, CliError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
    return 1


def _play(session) -> int:
    print(f"{session.campaign.title}\n{session.campaign.premise}\n")
    session, text = execute(session, "olhar")
    print(text)
    print("\nDigite 'ajuda' para os comandos.")
    while True:
        try:
            line = input("\n> ")
        except EOFError:
            print()
            break
        if line.strip().lower() in QUIT:
            break
        before = session.state
        try:
            session, text = execute(session, line)
        except CommandError as exc:
            print(f"erro: {exc}")
            continue
        save_game(session)
        output = format_output(session.narrator, before, session.state, text)
        if output:
            print(output)
        banner = status_banner(before, session.state)
        if banner:
            print(f"\n{banner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
