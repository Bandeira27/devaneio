"""Partida em disco: o arquivo da partida é a fonte da verdade, nada vive só em memória."""

from __future__ import annotations

import hashlib
import json
import os
import random
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from devaneio.engine import advance_beats, initial_state, reveal_facts
from devaneio.llm import ChatClient, LlmConfig, OpenAiCompatClient
from devaneio.narration import NarrationPack, Narrator
from devaneio.rules import RuleSystem, validate_state_against_rules
from devaneio.schema import Campaign, GameState, StrictModel, validate_against_campaign

from .content import joined, load_campaign_content
from .errors import GameError
from .table import TableMeta


class ContentHashes(StrictModel):
    """Impressão digital do conteúdo com que a partida foi jogada.

    Calculada sobre os modelos já mesclados. Serve só para avisar que o autor mudou o sistema ou a narração; nunca recusa a partida.
    """

    rules_sha256: str
    narration_sha256: str


class SaveFile(StrictModel):
    """Formato do arquivo de partida.

    A campanha não é copiada: fica o caminho, relativo ao arquivo da partida, para a partida
    poder ser movida junto com a campanha.
    """

    CAMPAIGN_PATH_FIELD: ClassVar[str] = "campaign_path"

    save_version: Literal[1] = 1
    campaign_path: str
    state: GameState
    # Mesa (jogo em grupo): opcional e aditivo; o CLI solo preserva o que não interpreta.
    table: TableMeta | None = None
    # Opcional: partidas antigas não têm e abrem sem aviso.
    content: ContentHashes | None = None


def saved_campaign_path(save_path: Path) -> Path | None:
    """O arquivo de campanha que uma partida usa, ou nada se o arquivo da partida não se lê.

    Lê só o campo ``campaign_path`` de ``SaveFile`` (relativo ao arquivo da partida), sem validar o estado todo.
    """
    try:
        raw = json.loads(save_path.read_text(encoding="utf-8"))[SaveFile.CAMPAIGN_PATH_FIELD]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return (save_path.parent / raw).resolve() if isinstance(raw, str) else None


def saved_table_summary(save_path: Path) -> tuple[Path, TableMeta] | None:
    """O arquivo de campanha e a mesa de uma partida, sem validar o estado todo; nada se não é uma mesa legível.

    Serve para listar mesas: lê só ``campaign_path`` e ``table`` (``TableMeta`` validada), sem carregar campanha nem regras.
    """
    try:
        raw = json.loads(save_path.read_text(encoding="utf-8"))
        campaign = raw[SaveFile.CAMPAIGN_PATH_FIELD]
        table = TableMeta.model_validate(raw["table"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(campaign, str):
        return None
    return (save_path.parent / campaign).resolve(), table


@dataclass
class Session:
    """Uma partida em memória: campanha, regras, estado e onde está gravada."""

    campaign: Campaign
    rules: RuleSystem
    state: GameState
    campaign_path: Path
    save_path: Path
    narrator: Narrator
    llm: ChatClient | None = None  # opcional; nunca gravado na partida
    table: TableMeta | None = None  # mesa em grupo; gravada junto com o estado
    # Avisos de ao abrir (conteúdo mudou desde o último salvamento); quem abre mostra.
    warnings: tuple[str, ...] = ()


def connect_llm(config: LlmConfig) -> ChatClient:
    """O cliente de LLM de uma configuração.

    É o único lugar que escolhe a implementação: CLI e servidor só pedem o cliente.
    """
    return OpenAiCompatClient(config)


def new_game(
    campaign_path: Path, save_path: Path, seed: int | None = None, *, start: bool = True
) -> Session:
    """Cria uma partida nova e a grava.

    Semente aleatória (< 2**53, portável) se não for dada. Com ``start=False`` a história ainda não
    começou: sem a abertura (marcos e fatos que já valem), que a mesa roda ao iniciar a partida.
    """
    campaign_path = Path(campaign_path).resolve()
    campaign, rules, pack = load_campaign_content(campaign_path)
    if seed is None:
        seed = random.SystemRandom().getrandbits(53)
    state = initial_state(campaign, rules, seed)
    if start:
        state, _ = advance_beats(state, campaign)
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
    """Carrega uma partida do arquivo.

    Com ``campaign_root``, a campanha referenciada pela partida precisa estar dentro dessa
    pasta: o caminho vem de dado (rule 05, item 10) e um servidor não pode deixá-lo apontar para
    fora. Sem raiz (CLI local), qualquer caminho relativo vale.
    """
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
        warnings=_content_warnings(data.content, content_hashes(rules, pack), rules, pack),
    )


def save_game(session: Session) -> None:
    """Grava a partida de forma atômica.

    Arquivo temporário na mesma pasta e ``os.replace``, para uma queda no meio nunca deixar a
    partida truncada.
    """
    relative = os.path.relpath(session.campaign_path, session.save_path.parent)
    payload = SaveFile(
        campaign_path=relative,
        state=session.state,
        table=session.table,
        content=content_hashes(session.rules, session.narrator.pack),
    )
    text = payload.model_dump_json(indent=2) + "\n"
    fd, temp = tempfile.mkstemp(dir=session.save_path.parent, prefix=".partida-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temp, session.save_path)
    except OSError:
        os.unlink(temp)
        raise


def content_hashes(rules: RuleSystem, pack: NarrationPack) -> ContentHashes:
    """As impressões digitais do sistema de regras e da narração, já mesclados."""
    return ContentHashes(rules_sha256=_digest(rules), narration_sha256=_digest(pack))


def _digest(model: RuleSystem | NarrationPack) -> str:
    # Ordenado e sem defaults: reordenar chaves ou ganhar campo com valor padrão não é mudança.
    dumped = model.model_dump(mode="json", exclude_defaults=True)
    text = json.dumps(dumped, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _content_warnings(
    saved: ContentHashes | None, now: ContentHashes, rules: RuleSystem, pack: NarrationPack
) -> tuple[str, ...]:
    if saved is None:
        return ()
    warnings = []
    if saved.rules_sha256 != now.rules_sha256:
        warnings.append(
            f"O sistema de regras '{rules.id}' mudou desde que esta partida foi salva: fórmulas, "
            "armas e dificuldades podem se comportar diferente do que o grupo já viveu."
        )
    if saved.narration_sha256 != now.narration_sha256:
        warnings.append(
            f"O pacote de narração '{pack.id}' mudou desde que esta partida foi salva: só o texto "
            "da narração muda, o jogo não."
        )
    return tuple(warnings)
