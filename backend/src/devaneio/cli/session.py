"""Partida em disco: o arquivo da partida é a fonte da verdade, nada vive só em memória."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from devaneio.engine import advance_beats, initial_state
from devaneio.rules import RuleSystem, load_builtin_rules, validate_campaign_against_rules
from devaneio.rules import validate_state_against_rules
from devaneio.schema import Campaign, GameState, StrictModel, load_campaign
from devaneio.schema import validate_against_campaign


class CliError(ValueError):
    """Problema ao criar ou abrir uma partida (arquivo incoerente, campanha incompatível)."""


class SaveFile(StrictModel):
    """Formato do arquivo de partida. A campanha não é copiada: fica o caminho, relativo
    ao arquivo da partida, para a partida poder ser movida junto com a campanha."""

    save_version: Literal[1] = 1
    campaign_path: str
    state: GameState


@dataclass
class Session:
    campaign: Campaign
    rules: RuleSystem
    state: GameState
    campaign_path: Path
    save_path: Path


def new_game(campaign_path: Path, save_path: Path, seed: int | None = None) -> Session:
    """Cria o estado inicial (com os marcos iniciais já ativos) e grava. Semente aleatória
    (< 2**53, portável) se não for dada."""
    campaign_path = Path(campaign_path).resolve()
    campaign, rules = _load_campaign_and_rules(campaign_path)
    if seed is None:
        seed = random.SystemRandom().getrandbits(53)
    state, _ = advance_beats(initial_state(campaign, rules, seed), campaign)
    session = Session(campaign, rules, state, campaign_path, Path(save_path).resolve())
    save_game(session)
    return session


def load_game(save_path: Path) -> Session:
    save_path = Path(save_path).resolve()
    data = SaveFile.model_validate_json(save_path.read_text(encoding="utf-8"))
    campaign_path = (save_path.parent / data.campaign_path).resolve()
    campaign, rules = _load_campaign_and_rules(campaign_path)
    errors = validate_against_campaign(data.state, campaign) + validate_state_against_rules(
        data.state, rules
    )
    if errors:
        raise CliError(_joined(f"partida '{save_path}' incoerente com a campanha/regras", errors))
    return Session(campaign, rules, data.state, campaign_path, save_path)


def save_game(session: Session) -> None:
    relative = os.path.relpath(session.campaign_path, session.save_path.parent)
    payload = SaveFile(campaign_path=relative, state=session.state)
    session.save_path.write_text(payload.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _load_campaign_and_rules(campaign_path: Path) -> tuple[Campaign, RuleSystem]:
    campaign = load_campaign(campaign_path.read_text(encoding="utf-8"))
    rules = load_builtin_rules(campaign.rules_id)
    errors = validate_campaign_against_rules(campaign, rules)
    if errors:
        raise CliError(_joined(f"campanha '{campaign.id}' incompatível com '{rules.id}'", errors))
    return campaign, rules


def _joined(head: str, errors: list[str]) -> str:
    return head + ":\n" + "\n".join(f"- {e}" for e in errors)
