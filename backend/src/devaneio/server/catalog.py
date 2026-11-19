"""Catálogo de campanhas lido de uma pasta.

Os arquivos de uma pasta, lidos na subida. A API só conhece campanhas por id; nenhum caminho vem da
requisição.
"""

from __future__ import annotations

import threading
from pathlib import Path

from pydantic import ValidationError

from devaneio.game import GameError, load_campaign_content
from devaneio.schema import Campaign, CampaignIntegrityError

from .models import CampaignSummary, summarize


class CatalogError(ValueError):
    """Pasta de campanhas inválida (arquivo malformado ou id repetido)."""


class Catalog:
    """As campanhas de uma pasta, lidas uma vez na subida do servidor."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self._lock = threading.Lock()
        self._paths: dict[str, Path] = {}
        self._summaries: list[CampaignSummary] = []
        for path in sorted(self.root.glob("*.json")):
            if (
                path.resolve().parent != self.root
            ):  # um link para fora da pasta: as mesas não o aceitariam
                raise CatalogError(f"campanha '{path.name}' aponta para fora da pasta de campanhas")
            campaign = self._load(path)
            if campaign.id in self._paths:
                raise CatalogError(
                    f"campanha '{campaign.id}' repetida: {self._paths[campaign.id].name} e {path.name}"
                )
            self._paths[campaign.id] = path
            self._summaries.append(summarize(campaign))

    @staticmethod
    def _load(path: Path) -> Campaign:
        try:
            return load_campaign_content(path)[0]
        except (ValidationError, CampaignIntegrityError, GameError, UnicodeDecodeError) as exc:
            raise CatalogError(f"campanha '{path.name}' inválida: {exc}") from exc

    def summaries(self) -> list[CampaignSummary]:
        """Título e premissa de cada campanha."""
        with self._lock:
            return list(self._summaries)

    def path(self, campaign_id: str) -> Path | None:
        """O arquivo de uma campanha pelo id, ou nada se o id não existe."""
        with self._lock:
            return self._paths.get(campaign_id)

    def relative(self, path: Path) -> str:
        """O caminho de uma campanha relativo à pasta do catálogo, com ``/``: é como as mesas a guardam.

        ``ValueError`` se o arquivo está fora da pasta.
        """
        return Path(path).resolve().relative_to(self.root).as_posix()

    def inside(self, relative: str) -> Path | None:
        """O arquivo de campanha de um caminho guardado, ou nada se ele sai da pasta do catálogo.

        O caminho vem de dado (rule 05, item 10): nunca absoluto, nunca com ``..`` que escape da pasta.
        """
        resolved = (self.root / relative).resolve()
        return resolved if resolved.is_relative_to(self.root) and resolved != self.root else None

    def register(self, path: Path) -> None:
        """Passa a conhecer (ou relê) uma campanha gravada depois da subida, sem reiniciar o servidor.

        O arquivo precisa estar na pasta do catálogo. Se já havia uma campanha com o mesmo id, ela é trocada.
        """
        resolved = Path(path).resolve()
        if resolved.parent != self.root:
            raise CatalogError("a campanha precisa estar na pasta do catálogo")
        campaign = self._load(resolved)
        with self._lock:
            other = self._paths.get(campaign.id)
            if other is not None and other != resolved:
                raise CatalogError(
                    f"campanha '{campaign.id}' repetida: {other.name} e {resolved.name}"
                )
            self._paths[campaign.id] = resolved
            self._summaries = [s for s in self._summaries if s.id != campaign.id]
            self._summaries.append(summarize(campaign))
            self._summaries.sort(key=lambda s: self._paths[s.id].name)
