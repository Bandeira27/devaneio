"""A partida: o que o jogo é, e como vira o arquivo de partida do CLI.

``Session`` e a montagem dela a partir de um ``SaveFile`` (``open_save``) e de volta (``build_save``) são puras: não sabem
onde a partida mora. O CLI as liga a um arquivo (``load_game``, ``save_game``); o servidor, ao banco dele.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

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

    save_version: Literal[1] = 1
    campaign_path: str
    state: GameState
    # Mesa (jogo em grupo): opcional e aditivo; o CLI solo preserva o que não interpreta.
    table: TableMeta | None = None
    # Opcional: partidas antigas não têm e abrem sem aviso.
    content: ContentHashes | None = None


@dataclass
class Session:
    """Uma partida em memória: campanha, regras, estado e, no CLI, o arquivo onde está gravada."""

    campaign: Campaign
    rules: RuleSystem
    state: GameState
    campaign_path: Path
    narrator: Narrator
    save_path: Path | None = None  # só a partida em arquivo (CLI); a do servidor mora no banco dele
    llm: ChatClient | None = None  # opcional; nunca gravado na partida
    table: TableMeta | None = None  # mesa em grupo; gravada junto com o estado
    # Avisos de ao abrir (conteúdo mudou desde o último salvamento); quem abre mostra.
    warnings: tuple[str, ...] = ()


def connect_llm(config: LlmConfig) -> ChatClient:
    """O cliente de LLM de uma configuração.

    É o único lugar que escolhe a implementação: CLI e servidor só pedem o cliente.
    """
    return OpenAiCompatClient(config)


def start_game(campaign_path: Path, seed: int | None = None, *, start: bool = True) -> Session:
    """Cria uma partida nova em memória, sem gravar em lugar nenhum.

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
    return Session(campaign, rules, state, campaign_path, Narrator(campaign, rules, pack))


def new_game(
    campaign_path: Path, save_path: Path, seed: int | None = None, *, start: bool = True
) -> Session:
    """Cria uma partida nova e a grava no arquivo."""
    session = replace(
        start_game(campaign_path, seed, start=start), save_path=Path(save_path).resolve()
    )
    save_game(session)
    return session


def open_save(data: SaveFile, campaign_path: Path, *, label: str) -> Session:
    """Monta a partida de um ``SaveFile``: carrega a campanha e confere o estado contra ela e as regras.

    ``campaign_path`` é onde a campanha está agora (quem guardou a partida sabe resolver o caminho dela, e
    decide se ele é permitido). ``label`` identifica a partida nas mensagens de erro. ``GameError`` se o estado
    não combina com a campanha ou com as regras.
    """
    campaign, rules, pack = load_campaign_content(campaign_path)
    errors = validate_against_campaign(data.state, campaign) + validate_state_against_rules(
        data.state, rules
    )
    if errors:
        raise GameError(joined(f"partida '{label}' incoerente com a campanha/regras", errors))
    return Session(
        campaign,
        rules,
        data.state,
        campaign_path,
        Narrator(campaign, rules, pack),
        table=data.table,
        warnings=_content_warnings(data.content, content_hashes(rules, pack), rules, pack),
    )


def build_save(session: Session, campaign_ref: str) -> SaveFile:
    """O ``SaveFile`` de uma partida: estado, mesa e as impressões digitais do conteúdo.

    ``campaign_ref`` é como quem guarda aponta para a campanha (no CLI, o caminho relativo ao arquivo).
    """
    return SaveFile(
        campaign_path=campaign_ref,
        state=session.state,
        table=session.table,
        content=content_hashes(session.rules, session.narrator.pack),
    )


def load_game(save_path: Path, *, campaign_root: Path | None = None) -> Session:
    """Carrega uma partida do arquivo.

    Com ``campaign_root``, a campanha referenciada pela partida precisa estar dentro dessa
    pasta: o caminho vem de dado (rule 05, item 10). Sem raiz (CLI local), qualquer caminho relativo vale.
    """
    save_path = Path(save_path).resolve()
    data = SaveFile.model_validate_json(save_path.read_text(encoding="utf-8"))
    campaign_path = (save_path.parent / data.campaign_path).resolve()
    if campaign_root is not None and not campaign_path.is_relative_to(
        Path(campaign_root).resolve()
    ):
        raise GameError(f"partida '{save_path}' aponta para uma campanha fora da pasta permitida")
    session = open_save(data, campaign_path, label=str(save_path))
    return replace(session, save_path=save_path)


def save_game(session: Session) -> None:
    """Grava a partida no arquivo dela, de forma atômica.

    Arquivo temporário na mesma pasta e ``os.replace``, para uma queda no meio nunca deixar a
    partida truncada.
    """
    if session.save_path is None:
        raise GameError("esta partida não tem arquivo: ela mora no banco do servidor")
    relative = os.path.relpath(session.campaign_path, session.save_path.parent)
    text = build_save(session, relative).model_dump_json(indent=2) + "\n"
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
