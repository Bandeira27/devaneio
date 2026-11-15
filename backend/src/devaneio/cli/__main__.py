"""``python -m devaneio.cli nova <campanha.json> <partida.json> [--seed N]``
``python -m devaneio.cli jogar <partida.json>``"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace
from pathlib import Path

from pydantic import ValidationError

from devaneio.game import (
    CommandError,
    GameError,
    Session,
    connect_llm,
    execute,
    format_output,
    is_command,
    load_game,
    new_game,
    run_freeform,
    save_game,
    status_banner,
)
from devaneio.llm import LlmConfig, LlmError
from devaneio.schema import CampaignIntegrityError

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
    play.add_argument("--sem-llm", action="store_true", help="ignora o LLM configurado no ambiente")

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
        session = load_game(args.partida)
        if not args.sem_llm:
            config = LlmConfig.from_env(os.environ)
            if config is not None:
                session = replace(session, llm=connect_llm(config))
        return _play(session)
    except FileNotFoundError as exc:
        print(f"erro: arquivo não encontrado: {exc.filename}", file=sys.stderr)
    except (ValidationError, CampaignIntegrityError, GameError, LlmError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
    return 1


def _play(session: Session) -> int:
    print(f"{session.campaign.title}\n{session.campaign.premise}\n")
    session, text = execute(session, "olhar")
    print(text)
    print("\nDigite 'ajuda' para os comandos.")
    if session.llm is not None:
        print(
            f"LLM ligado ({session.llm.description}): escreva livremente e o mestre propõe as ações. "
            "O contexto da partida é enviado a esse servidor."
        )
    while True:
        try:
            line = input("\n> ")
        except EOFError:
            print()
            break
        if line.strip().lower() in QUIT:
            break
        before = session.state
        say = ""
        commands: tuple[str, ...] = ()
        try:
            if session.llm is not None and line.strip() and not is_command(line):
                result = run_freeform(session, line)
                session, say, commands, text = result.session, result.say, result.commands, ""
            else:
                session, text = execute(session, line)
        except CommandError as exc:
            print(f"erro: {exc}")
            continue
        save_game(session)
        if say:
            print(f"Mestre: {say}")
        if commands:
            print(f"  (ações propostas: {'; '.join(commands)})")
        output = format_output(session.narrator, before, session.state, text, session.llm)
        if output:
            print(output)
        banner = status_banner(before, session.state)
        if banner:
            print(f"\n{banner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
