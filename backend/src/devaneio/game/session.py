"""Partida em disco: o arquivo da partida é a fonte da verdade, nada vive só em memória."""

from __future__ import annotations

import os
import random
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from devaneio.engine import advance_beats, initial_state, reveal_facts
from devaneio.llm import ChatClient, LlmConfig, OpenAiCompatClient
from devaneio.narration import Narrator
from devaneio.rules import RuleSystem, validate_state_against_rules
from devaneio.schema import Campaign, GameState, StrictModel, validate_against_campaign

from .content import joined, load_campaign_content
from .errors import GameError
from .table import TableMeta


class SaveFile(StrictModel):
    """Formato do arquivo de partida. A campanha não é copiada: fica o caminho, relativo
    ao arquivo da partida, para a partida poder ser movida junto com a campanha."""

    save_version: Literal[1] = 1
    campaign_path: str
    state: GameState
    # Mesa (jogo em grupo): opcional e aditivo; o CLI solo preserva o que não interpreta.
    table: TableMeta | None = None


@dataclass
class Session:
    campaign: Campaign
    rules: RuleSystem
    state: GameState
    campaign_path: Path
    save_path: Path
    narrator: Narrator
    llm: ChatClient | None = None  # opcional; nunca gravado na partida
    table: TableMeta | None = None  # mesa em grupo; gravada junto com o estado


def connect_llm(config: LlmConfig) -> ChatClient:
    """O cliente de LLM de uma configuração. É o único lugar que escolhe a implementação:
    CLI e servidor só pedem o cliente."""
    return OpenAiCompatClient(config)


def new_game(campaign_path: Path, save_path: Path, seed: int | None = None) -> Session:
    """Cria o estado inicial (com os marcos iniciais já ativos) e grava. Semente aleatória
    (< 2**53, portável) se não for dada."""
    campaign_path = Path(campaign_path).resolve()
    campaign, rules, pack = load_campaign_content(campaign_path)
    if seed is None:
        seed = random.SystemRandom().getrandbits(53)
    state, _ = advance_beats(initial_state(campaign, rules, seed), campaign)
    state, _ = reveal_facts(state, campaign)
    session = Session(
        campaign,
        rules,
        state,
        campaign_path,
        Path(save_path).resolve(),
        Narrator(campaign, rules, pack),
    )
    save_game(session)
    return session


def load_game(save_path: Path, *, campaign_root: Path | None = None) -> Session:
    """Com ``campaign_root``, a campanha referenciada pela partida precisa estar dentro
    dessa pasta: o caminho vem de dado (rule 05, item 10) e um servidor não pode deixá-lo
    apontar para fora. Sem raiz (CLI local), qualquer caminho relativo vale."""
    save_path = Path(save_path).resolve()
    data = SaveFile.model_validate_json(save_path.read_text(encoding="utf-8"))
    campaign_path = (save_path.parent / data.campaign_path).resolve()
    if campaign_root is not None and not campaign_path.is_relative_to(
        Path(campaign_root).resolve()
    ):
        raise GameError(f"partida '{save_path}' aponta para uma campanha fora da pasta permitida")
    campaign, rules, pack = load_campaign_content(campaign_path)
    errors = validate_against_campaign(data.state, campaign) + validate_state_against_rules(
        data.state, rules
    )
    if errors:
        raise GameError(joined(f"partida '{save_path}' incoerente com a campanha/regras", errors))
    return Session(
        campaign,
        rules,
        data.state,
        campaign_path,
        save_path,
        Narrator(campaign, rules, pack),
        table=data.table,
    )


def save_game(session: Session) -> None:
    """Escrita atômica: arquivo temporário na mesma pasta e ``os.replace``, para uma queda
    no meio nunca deixar a partida truncada."""
    relative = os.path.relpath(session.campaign_path, session.save_path.parent)
    payload = SaveFile(campaign_path=relative, state=session.state, table=session.table)
    text = payload.model_dump_json(indent=2) + "\n"
    fd, temp = tempfile.mkstemp(dir=session.save_path.parent, prefix=".partida-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temp, session.save_path)
    except OSError:
        os.unlink(temp)
        raise
