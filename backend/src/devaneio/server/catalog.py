"""Catálogo de campanhas: os arquivos de uma pasta, lidos na subida. A API só conhece
campanhas por id; nenhum caminho vem da requisição."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from devaneio.schema import Campaign, CampaignIntegrityError, load_campaign

from .models import CampaignSummary, summarize


class CatalogError(ValueError):
    """Pasta de campanhas inválida (arquivo malformado ou id repetido)."""


class Catalog:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self._paths: dict[str, Path] = {}
        self._summaries: list[CampaignSummary] = []
        for path in sorted(self.root.glob("*.json")):
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
            return load_campaign(path.read_text(encoding="utf-8"))
        except (ValidationError, CampaignIntegrityError, UnicodeDecodeError) as exc:
            raise CatalogError(f"campanha '{path.name}' inválida: {exc}") from exc

    def summaries(self) -> list[CampaignSummary]:
        return list(self._summaries)

    def path(self, campaign_id: str) -> Path | None:
        return self._paths.get(campaign_id)
