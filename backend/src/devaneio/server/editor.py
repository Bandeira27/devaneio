"""O editor de campanhas: validar, listar, criar e regravar arquivos da pasta de campanhas.

Está sempre ligado (``--sem-editor`` desliga), mas só atende pedidos vindos da própria máquina (rule 05,
item 25). O único dado da requisição que vira nome de arquivo é o id da campanha, um slug: o arquivo é
sempre ``<pasta>/<id>.json``. A escrita é atômica e só acontece sem erro de validação; campanha que
alguma mesa usa não é sobrescrita, porque as mesas a relêem do arquivo.
"""

from __future__ import annotations

import ipaddress
import json
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from devaneio.game import (
    GameError,
    check_campaign_data,
    load_rules_by_id,
    preview_contexts,
    rules_ids,
)
from devaneio.schema import ID_REGEX, Campaign, CampaignIntegrityError, load_campaign

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
MAX_ID = 64
CAMPAIGN_ID = ID_REGEX  # o id vira nome de arquivo: o mesmo slug do esquema, conferido por inteiro


# Quem põe um proxy ou túnel na frente do servidor faz todo pedido parecer local: esses cabeçalhos o denunciam.
FORWARDING_HEADERS = (
    "Forwarded",
    "X-Forwarded-For",
    "X-Forwarded-Host",
    "X-Forwarded-Proto",
    "X-Real-IP",
)


def is_loopback(host: str) -> bool:
    """O endereço de escuta é só desta máquina (``127.0.0.1``, ``::1`` ou ``localhost``)."""
    return host.strip().lower() in LOOPBACK_NAMES


def peer_is_local(address: str) -> bool:
    """O endereço de quem se conectou (ou em que o servidor escuta) é desta máquina.

    Vale ``127.0.0.0/8`` e ``::1``, inclusive o IPv4 mapeado em IPv6 (``::ffff:127.0.0.1``). O endereço da
    própria rede (``192.168.x.x``) não vale, mesmo sendo desta máquina: abra o app por ``localhost``.
    """
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])  # sem o escopo de ``fe80::1%eth0``
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback


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
        self._write_lock = (
            threading.Lock()
        )  # create e update: checar, gravar e registrar sem outro editor no meio

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
        if not CAMPAIGN_ID.fullmatch(rules_id) or len(rules_id) > MAX_ID:
            raise ApiFailure(404, "not_found", "sistema desconhecido")
        try:
            return RulesView.of(load_rules_by_id(rules_id, self.root))
        except GameError:
            raise ApiFailure(404, "not_found", "sistema desconhecido") from None

    # --- validação ---------------------------------------------------------------

    def validate(self, data: dict[str, Any]) -> ValidationReport:
        """Confere a campanha como o servidor a confere ao carregar uma mesa, em português."""
        report, _, _ = self._check(data)
        return report

    def _check(self, data: dict[str, Any]) -> tuple[ValidationReport, Campaign | None, Any]:
        result = check_campaign_data(data, self.root)
        errors = [ValidationIssue(path=p, message=m) for p, m in result.errors]
        if result.campaign is not None and len(result.campaign.id) > MAX_ID:
            errors.append(
                ValidationIssue(
                    path="id", message=f"'id' passa de {MAX_ID} caracteres (vira o nome do arquivo)"
                )
            )
        findings = [AuthoringFinding(level=f.level, text=f.text) for f in result.findings]
        report = ValidationReport(ok=not errors, errors=errors, findings=findings)
        return report, (result.campaign if not errors else None), result.rules

    # --- escrita -----------------------------------------------------------------

    def create(self, data: dict[str, Any]) -> EditorCampaign:
        """Grava uma campanha nova; o id não pode existir (nem por um pedido simultâneo)."""
        campaign, _ = self._valid(data)
        path = self._path_for(campaign.id)
        with self._write_lock:
            return self._write(campaign, path, replace=False)

    def update(self, campaign_id: str, data: dict[str, Any]) -> EditorCampaign:
        """Regrava uma campanha que nenhuma mesa usa; o id não muda."""
        path = self._known_path(campaign_id)
        campaign, _ = self._valid(data)
        if campaign.id != campaign_id:
            raise ApiFailure(
                409, "campaign_id_changed", "o id de uma campanha não muda: salve uma cópia"
            )
        with self._write_lock:
            if path in self.storage.campaigns_in_use():
                raise ApiFailure(
                    409,
                    "campaign_in_use",
                    "esta campanha já tem mesa e é relida por ela: salve uma cópia com outro id",
                )
            return self._write(campaign, path, replace=True)

    def _valid(self, data: dict[str, Any]) -> tuple[Campaign, Any]:
        report, campaign, rules = self._check(data)
        if campaign is None:
            raise ApiFailure(
                422,
                "campaign_invalid",
                f"a campanha tem {len(report.errors)} erro(s); corrija antes de salvar",
            )
        return campaign, rules

    def _write(self, campaign: Campaign, path: Path, *, replace: bool) -> EditorCampaign:
        """Grava num temporário da mesma pasta e troca de uma vez; sem ``replace``, falha se o arquivo já existe."""
        try:
            text = json.dumps(campaign.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
            payload = text.encode("utf-8")
        except (ValueError, UnicodeError):
            raise ApiFailure(
                422, "campaign_invalid", "a campanha tem caracteres que não podem ser gravados"
            ) from None
        temp: Path | None = None
        try:
            handle, temp_name = tempfile.mkstemp(dir=self.root, prefix=".editor-", suffix=".tmp")
            temp = Path(temp_name)
            with os.fdopen(handle, "wb") as out:
                out.write(payload)
            if path.exists():
                shutil.copymode(
                    path, temp
                )  # mkstemp cria 0600: o arquivo regravado mantém a permissão que tinha
            else:
                temp.chmod(0o644)
            if replace:
                os.replace(temp, path)
            else:
                os.link(
                    temp, path
                )  # falha se já existe: dois pedidos com o mesmo id não se sobrescrevem
        except FileExistsError:
            raise ApiFailure(
                409, "campaign_exists", f"já existe uma campanha '{campaign.id}'; escolha outro id"
            ) from None
        except OSError as exc:
            raise ApiFailure(500, "internal", "não foi possível gravar a campanha") from exc
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        try:
            self.catalog.register(path)
        except (CatalogError, OSError) as exc:
            raise ApiFailure(
                500,
                "internal",
                "a campanha foi gravada, mas o catálogo não a leu; reinicie o servidor",
            ) from exc
        writable = path not in self.storage.campaigns_in_use()
        return EditorCampaign(id=campaign.id, title=campaign.title, writable=writable)

    # --- prévia ------------------------------------------------------------------

    def preview(self, data: dict[str, Any]) -> PreviewView:
        """O que o jogador e o LLM veem desta campanha; não grava nada."""
        campaign, rules = self._valid(data)
        contexts = preview_contexts(campaign, rules)
        return PreviewView(
            player=CampaignView.of(campaign, contexts.state),
            llm=_pretty(contexts.llm),
            llm_secrets=_pretty(contexts.llm_secrets),
            copilot_chars=contexts.copilot_chars,
            copilot_limit=contexts.copilot_limit,
        )

    # --- caminho -----------------------------------------------------------------

    def _path_for(self, campaign_id: str) -> Path:
        """``<pasta>/<id>.json`` para um id em forma de slug; qualquer outra coisa é recusada."""
        if not CAMPAIGN_ID.fullmatch(campaign_id) or len(campaign_id) > MAX_ID:
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
