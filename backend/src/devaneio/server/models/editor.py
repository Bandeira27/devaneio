"""O editor de campanhas: o que entra e o que sai das rotas `/editor/*`."""

from __future__ import annotations

from typing import Any, Literal

from devaneio.schema import Id, StrictModel

from .campaign import CampaignView


class EditorCampaign(StrictModel):
    """Uma campanha da pasta, como o editor a lista.

    ``writable`` é falso quando alguma mesa já usa o arquivo: o editor não o sobrescreve, só copia.
    """

    id: Id
    title: str
    writable: bool


class ValidateRequest(StrictModel):
    """A campanha como o editor a tem agora, ainda sem passar pela validação (JSON cru)."""

    campaign: dict[str, Any]


class SaveRequest(StrictModel):
    """A campanha a gravar: o servidor a valida de novo e só grava sem erro."""

    campaign: dict[str, Any]


class ValidationIssue(StrictModel):
    """Um erro que impede de salvar: o caminho do campo (`locations.2.name`, vazio se é geral) e a frase."""

    path: str
    message: str


class AuthoringFinding(StrictModel):
    """Um achado de autoria: `erro` impede a campanha de funcionar como esperado; `aviso` é um risco aceitável."""

    level: Literal["erro", "aviso"]
    text: str


class ValidationReport(StrictModel):
    """O resultado da validação: `ok` quando não há erro (os achados de autoria podem existir mesmo assim)."""

    ok: bool
    errors: list[ValidationIssue]
    findings: list[AuthoringFinding]


class SystemInfo(StrictModel):
    """Um sistema de regras que a campanha pode citar."""

    id: Id
    name: str


class PreviewView(StrictModel):
    """O que cada um enxerga da campanha: o jogador, o LLM sem e com segredos, e o contexto do copiloto.

    ``llm`` é o contexto público; ``llm_secrets`` o que o LLM recebe com ``--segredos-no-llm``. O contexto do
    copiloto (a campanha inteira) tem ``copilot_chars`` caracteres para um teto de ``copilot_limit``.
    """

    player: CampaignView
    llm: str
    llm_secrets: str
    copilot_chars: int
    copilot_limit: int
