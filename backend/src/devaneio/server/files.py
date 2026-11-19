"""Arquivos e pasta de dados privados do servidor: dono único, modo fechado desde a criação.

Serve ao banco (``devaneio.db`` e os auxiliares) e à chave do LLM (``llm.key``), que não é do banco.
Em Windows os modos POSIX não valem; a proteção é a do perfil do usuário.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from .errors import DatabaseError

POSIX = os.name == "posix"
DIR_MODE = 0o700
FILE_MODE = 0o600
GROUP_AND_OTHERS = 0o077


def prepare_data_dir(data_dir: Path) -> Path:
    """Cria a pasta de dados só do dono (``0700``) ou confere a que já existe.

    Dono diferente é recusa. Pasta nossa e aberta a outros é fechada, com aviso: ali ficam tokens
    (em hash) e a chave do LLM, e nada disso é para outro usuário da máquina.
    """
    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
    _own_and_tighten(data_dir, DIR_MODE, "a pasta de dados")
    return data_dir


def create_private_file(path: Path, *, exclusive: bool = False) -> None:
    """Cria o arquivo vazio com ``0600`` desde o primeiro instante, se ainda não existe.

    Com ``exclusive``, um arquivo que já existe (ou aparece entre a checagem e a criação) é ``FileExistsError``,
    nunca aberto: quem pede não sobrescreve nada.
    """
    flags = os.O_RDWR | os.O_CREAT | (os.O_EXCL if exclusive else 0)
    try:
        os.close(os.open(path, flags, FILE_MODE))
    except FileExistsError:
        raise
    except OSError as exc:
        raise DatabaseError(f"não consegui criar {path.name}: {exc.strerror}") from exc


def tighten(path: Path, label: str) -> None:
    """Garante que um arquivo é do dono e só dele (``0600``); corrige e avisa se estava aberto."""
    _own_and_tighten(path, FILE_MODE, label)


def _own_and_tighten(path: Path, mode: int, label: str) -> None:
    if not POSIX:
        return
    info = path.stat()
    if info.st_uid != os.getuid():
        raise DatabaseError(f"{label} ({path.name}) pertence a outro usuário: recusando usar")
    if stat.S_IMODE(info.st_mode) & GROUP_AND_OTHERS:
        path.chmod(mode)
        print(
            f"aviso: {label} ({path.name}) estava aberto a outros usuários; fechei.",
            file=sys.stderr,
        )
