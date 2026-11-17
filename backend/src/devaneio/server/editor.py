"""O editor de campanhas: validar, listar, criar e regravar arquivos da pasta de campanhas.

Só existe com ``--editor`` e em localhost (rule 05, item 25). O único dado da requisição que vira nome
de arquivo é o id da campanha, um slug: o arquivo é sempre ``<pasta>/<id>.json``. A escrita é atômica
e só acontece sem erro de validação; campanha que alguma mesa usa não é sobrescrita, porque as mesas
a relêem do arquivo.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from devaneio.engine import initial_state
from devaneio.game import (
    GameError,
    check_content,
    explain_validation_error,
    load_pack_for,
    load_rules_by_id,
    load_rules_for,
    rules_ids,
)
from devaneio.llm.copilot import MAX_CONTEXT_CHARS, build_copilot_context
from devaneio.llm.prompts import build_context
from devaneio.rules import validate_campaign_against_rules
from devaneio.schema import Campaign, CampaignIntegrityError, Character, load_campaign

from .catalog import Catalog, CatalogError
from .errors import ApiFailure
from .models import (
    AuthoringFinding,
    CampaignView,
    EditorCampaign,
    PreviewView,
    RulesView,
    SystemInfo,
    ValidationIssue,
    ValidationReport,
)
from .storage import Storage

MAX_EDITOR_BODY = 512 * 1024
LOOPBACK_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})
CAMPAIGN_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
MAX_ID = 64
PREVIEW_SEED = 0


def is_loopback(host: str) -> bool:
    """O endereço de escuta é só desta máquina (``127.0.0.1``, ``::1`` ou ``localhost``)."""
    return host.strip().lower() in LOOPBACK_NAMES


def host_allowed(header: str | None, port: int) -> bool:
    """O cabeçalho ``Host`` é um nome local com a porta do servidor (contra DNS rebinding)."""
    if not header:
        return False
    value = header.strip().lower()
    if value.startswith("["):  # [::1]:porta
        name, _, rest = value[1:].partition("]")
        given = rest[1:] if rest.startswith(":") else ""
        valid_rest = rest == "" or rest.startswith(":")
    else:
        name, _, given = value.partition(":")
        valid_rest = True
    if not valid_rest or name not in LOOPBACK_NAMES:
        return False
    if given == "":
        return port == 80
    return given.isascii() and given.isdigit() and int(given) == port


def origin_allowed(origin: str | None, host_header: str | None) -> bool:
    """Sem ``Origin`` vale (cliente que não é navegador); com ele, precisa ser o próprio servidor (contra CSRF)."""
    if origin is None:
        return True
    return (
        host_header is not None
        and origin.strip().lower() == f"http://{host_header.strip().lower()}"
    )


class EditorService:
    """As operações do editor sobre a pasta de campanhas, sem HTTP."""

    def __init__(self, catalog: Catalog, storage: Storage) -> None:
        self.catalog = catalog
        self.storage = storage
        self.root = catalog.root

    # --- leitura -----------------------------------------------------------------

    def list_campaigns(self) -> list[EditorCampaign]:
        """As campanhas da pasta, marcando as que alguma mesa já usa."""
        used = self.storage.campaigns_in_use()
        out = []
        for summary in self.catalog.summaries():
            path = self.catalog.path(summary.id)
            if path is not None:
                out.append(
                    EditorCampaign(id=summary.id, title=summary.title, writable=path not in used)
                )
        return out

    def get_campaign(self, campaign_id: str) -> Campaign:
        """A campanha inteira, lida do arquivo."""
        path = self._known_path(campaign_id)
        try:
            return load_campaign(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, CampaignIntegrityError) as exc:
            raise ApiFailure(
                409, "campaign_unreadable", f"não foi possível ler a campanha '{campaign_id}'"
            ) from exc

    def systems(self) -> list[SystemInfo]:
        """Os sistemas de regras que uma campanha pode citar."""
        out = []
        for rules_id in rules_ids(self.root):
            try:
                out.append(SystemInfo(id=rules_id, name=load_rules_by_id(rules_id, self.root).name))
            except GameError:
                continue  # sistema do autor com erro: o validador da campanha explica quando ele for citado
        return out

    def system(self, rules_id: str) -> RulesView:
        """As regras de um sistema (habilidades, dificuldades...) para montar condições."""
        if not CAMPAIGN_ID.match(rules_id) or len(rules_id) > MAX_ID:
            raise ApiFailure(404, "not_found", "sistema desconhecido")
        try:
            return RulesView.of(load_rules_by_id(rules_id, self.root))
        except GameError:
            raise ApiFailure(404, "not_found", "sistema desconhecido") from None

    # --- validação ---------------------------------------------------------------

    def validate(self, data: dict[str, Any]) -> ValidationReport:
        """Confere a campanha como o servidor a confere ao carregar uma mesa, em português."""
        report, _ = self._check(data)
        return report

    def _check(self, data: dict[str, Any]) -> tuple[ValidationReport, Campaign | None]:
        errors: list[ValidationIssue] = []
        findings: list[AuthoringFinding] = []
        campaign: Campaign | None = None
        try:
            campaign = load_campaign(data)
        except ValidationError as exc:
            errors += [ValidationIssue(path=p, message=m) for p, m in explain_validation_error(exc)]
        except CampaignIntegrityError as exc:
            errors += [ValidationIssue(path="", message=m) for m in exc.errors]
        else:
            if len(campaign.id) > MAX_ID:
                errors.append(
                    ValidationIssue(
                        path="id",
                        message=f"'id' passa de {MAX_ID} caracteres (vira o nome do arquivo)",
                    )
                )
            try:
                rules = load_rules_for(campaign, self.root)
                pack = load_pack_for(campaign, self.root)
            except GameError as exc:
                errors.append(ValidationIssue(path="", message=str(exc)))
            else:
                errors += [
                    ValidationIssue(path="", message=m)
                    for m in validate_campaign_against_rules(campaign, rules)
                ]
                findings = [
                    AuthoringFinding(level=f.level, text=f.text)
                    for f in check_content(campaign, rules, pack)
                ]
        ok = not errors
        return ValidationReport(ok=ok, errors=errors, findings=findings), campaign if ok else None

    # --- escrita -----------------------------------------------------------------

    def create(self, data: dict[str, Any]) -> EditorCampaign:
        """Grava uma campanha nova; o id não pode existir."""
        campaign = self._valid(data)
        path = self._path_for(campaign.id)
        if path.exists():
            raise ApiFailure(
                409, "campaign_exists", f"já existe uma campanha '{campaign.id}'; escolha outro id"
            )
        return self._write(campaign, path)

    def update(self, campaign_id: str, data: dict[str, Any]) -> EditorCampaign:
        """Regrava uma campanha que nenhuma mesa usa; o id não muda."""
        path = self._known_path(campaign_id)
        campaign = self._valid(data)
        if campaign.id != campaign_id:
            raise ApiFailure(
                409, "campaign_id_changed", "o id de uma campanha não muda: salve uma cópia"
            )
        if path in self.storage.campaigns_in_use():
            raise ApiFailure(
                409,
                "campaign_in_use",
                "esta campanha já tem mesa e é relida por ela: salve uma cópia com outro id",
            )
        return self._write(campaign, path)

    def _valid(self, data: dict[str, Any]) -> Campaign:
        report, campaign = self._check(data)
        if campaign is None:
            raise ApiFailure(
                422,
                "campaign_invalid",
                f"a campanha tem {len(report.errors)} erro(s); corrija antes de salvar",
            )
        return campaign

    def _write(self, campaign: Campaign, path: Path) -> EditorCampaign:
        text = json.dumps(campaign.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
        handle, temp_name = tempfile.mkstemp(dir=self.root, prefix=".editor-", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                out.write(text)
            os.replace(temp_name, path)
        except OSError as exc:
            Path(temp_name).unlink(missing_ok=True)
            raise ApiFailure(500, "internal", "não foi possível gravar a campanha") from exc
        try:
            self.catalog.register(path)
        except CatalogError as exc:
            raise ApiFailure(409, "campaign_exists", str(exc)) from exc
        writable = path not in self.storage.campaigns_in_use()
        return EditorCampaign(id=campaign.id, title=campaign.title, writable=writable)

    # --- prévia ------------------------------------------------------------------

    def preview(self, data: dict[str, Any]) -> PreviewView:
        """O que o jogador e o LLM veem desta campanha; não grava nada."""
        campaign = self._valid(data)
        rules = load_rules_for(campaign, self.root)
        hero = Character(
            id="jogador",
            name="Jogador",
            attributes={a.id: a.default for a in rules.attributes},
            hp=1,
            max_hp=1,
        )
        state = initial_state(campaign, rules, PREVIEW_SEED, [hero])
        public = build_context(campaign, rules, state, hero.id, include_private=False)
        private = build_context(campaign, rules, state, hero.id, include_private=True)
        copilot = build_copilot_context(campaign, rules, state)
        return PreviewView(
            player=CampaignView.of(campaign, state),
            llm=_pretty(public),
            llm_secrets=_pretty(private),
            copilot_chars=len(json.dumps(copilot, ensure_ascii=False, separators=(",", ":"))),
            copilot_limit=MAX_CONTEXT_CHARS,
        )

    # --- caminho -----------------------------------------------------------------

    def _path_for(self, campaign_id: str) -> Path:
        """``<pasta>/<id>.json`` para um id em forma de slug; qualquer outra coisa é recusada."""
        if not CAMPAIGN_ID.match(campaign_id) or len(campaign_id) > MAX_ID:
            raise ApiFailure(404, "not_found", "campanha desconhecida")
        path = (self.root / f"{campaign_id}.json").resolve()
        if path.parent != self.root:
            raise ApiFailure(404, "not_found", "campanha desconhecida")
        return path

    def _known_path(self, campaign_id: str) -> Path:
        self._path_for(campaign_id)  # recusa o que não é slug antes de olhar o catálogo
        path = self.catalog.path(campaign_id)
        if path is None:
            raise ApiFailure(404, "not_found", "campanha desconhecida")
        return path


def _pretty(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=False, indent=2)
