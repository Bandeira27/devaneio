"""Adaptador HTTP sobre ``TableService``: roteamento, JSON e mapeamento de erros.

Só biblioteca padrão (``http.server``). O handler é a fronteira de execução: qualquer
exceção não prevista vira ``500`` genérico com traceback no stderr, nunca no corpo.
"""

from __future__ import annotations

import json
import re
import socket
import sys
import traceback
from collections.abc import Callable, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TypeAlias, TypeVar
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, ValidationError

from .app import TableService
from .auth import bearer_token
from .editor import MAX_EDITOR_BODY, EditorService, host_allowed, origin_allowed
from .errors import ApiFailure
from .models import (
    ApiError,
    CommandRequest,
    CopilotRequest,
    CreateTableRequest,
    ErrorResponse,
    InvitePreviewRequest,
    JoinRequest,
    LifecycleRequest,
    SaveRequest,
    SayRequest,
    ValidateRequest,
)
from .static import MAX_STATIC_BYTES, SECURITY_HEADERS, StaticFile, StaticSite

MAX_BODY = 64 * 1024
MAX_WAIT = 30  # segundos de long-poll
JSON = "application/json"
M = TypeVar("M", bound=BaseModel)

Payload: TypeAlias = BaseModel | Sequence[BaseModel]
Route: TypeAlias = tuple[
    str, re.Pattern[str], Callable[["Handler", re.Match[str]], "tuple[int, Payload]"]
]


class ApiServer(ThreadingHTTPServer):
    """Servidor HTTP com uma thread por conexão, ligado ao serviço da mesa."""

    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        service: TableService,
        static: StaticSite | None = None,
        editor: EditorService | None = None,
    ) -> None:
        if ":" in address[0]:
            self.address_family = socket.AF_INET6  # --host ::1
        super().__init__(address, Handler)
        self.service = service
        self.static = static  # o front, só com --web; sem ele a API é só JSON
        self.editor = editor  # só com --editor (e só em loopback): sem ele, /editor/* é 404


class Handler(BaseHTTPRequestHandler):
    """Traduz requisições HTTP em chamadas ao serviço e as respostas em JSON ou arquivo."""

    server: ApiServer
    server_version = "devaneio"
    sys_version = ""
    timeout = 15  # segundos sem dados na conexão: cliente que some não prende a thread
    protocol_version = "HTTP/1.1"
    _body_read = False  # o corpo do pedido já foi lido? (senão, recusar exige fechar a conexão)

    # --- rotas -------------------------------------------------------------------

    def _campaigns(self, _match: re.Match[str]) -> tuple[int, Payload]:
        return 200, self.server.service.list_campaigns()

    def _create_table(self, _match: re.Match[str]) -> tuple[int, Payload]:
        request = self._read_json(CreateTableRequest)
        return 201, self.server.service.create_table(request)

    def _get_table(self, match: re.Match[str]) -> tuple[int, Payload]:
        return 200, self.server.service.get_table(match.group(1), self._token())

    def _get_campaign(self, match: re.Match[str]) -> tuple[int, Payload]:
        return 200, self.server.service.get_campaign(match.group(1), self._token())

    def _get_rules(self, match: re.Match[str]) -> tuple[int, Payload]:
        return 200, self.server.service.get_rules(match.group(1), self._token())

    def _preview_invite(self, match: re.Match[str]) -> tuple[int, Payload]:
        request = self._read_json(InvitePreviewRequest)
        return 200, self.server.service.preview_invite(match.group(1), request)

    def _join_table(self, match: re.Match[str]) -> tuple[int, Payload]:
        request = self._read_json(JoinRequest)
        return 201, self.server.service.join_table(match.group(1), request)

    def _command(self, match: re.Match[str]) -> tuple[int, Payload]:
        request = self._read_json(CommandRequest)
        return 200, self.server.service.run_command(match.group(1), self._token(), request)

    def _lifecycle(self, match: re.Match[str]) -> tuple[int, Payload]:
        request = self._read_json(LifecycleRequest)
        return 200, self.server.service.set_phase(match.group(1), self._token(), request)

    def _say(self, match: re.Match[str]) -> tuple[int, Payload]:
        request = self._read_json(SayRequest)
        return 200, self.server.service.say(match.group(1), self._token(), request)

    def _copilot(self, match: re.Match[str]) -> tuple[int, Payload]:
        request = self._read_json(CopilotRequest)
        return 200, self.server.service.copilot(match.group(1), self._token(), request)

    def _get_events(self, match: re.Match[str]) -> tuple[int, Payload]:
        since = self._query_int("since", default=0)
        since_talk = self._query_int("since_talk", default=0, max_digits=16)
        wait = self._query_int("wait", default=0)
        if wait > MAX_WAIT:
            raise ApiFailure(400, "bad_request", f"'wait' vai de 0 a {MAX_WAIT} segundos")
        return 200, self.server.service.get_events(
            match.group(1), self._token(), since, wait=wait, since_talk=since_talk
        )

    # --- editor (só com --editor) -------------------------------------------------

    def _editor(self) -> EditorService:
        editor = self.server.editor
        if editor is None:
            raise ApiFailure(404, "not_found", f"rota desconhecida: {urlsplit(self.path).path}")
        return editor

    def _editor_campaigns(self, _match: re.Match[str]) -> tuple[int, Payload]:
        return 200, self._editor().list_campaigns()

    def _editor_get(self, match: re.Match[str]) -> tuple[int, Payload]:
        return 200, self._editor().get_campaign(match.group(1))

    def _editor_validate(self, _match: re.Match[str]) -> tuple[int, Payload]:
        request = self._read_json(ValidateRequest, limit=MAX_EDITOR_BODY)
        return 200, self._editor().validate(request.campaign)

    def _editor_create(self, _match: re.Match[str]) -> tuple[int, Payload]:
        request = self._read_json(SaveRequest, limit=MAX_EDITOR_BODY)
        return 201, self._editor().create(request.campaign)

    def _editor_update(self, match: re.Match[str]) -> tuple[int, Payload]:
        request = self._read_json(SaveRequest, limit=MAX_EDITOR_BODY)
        return 200, self._editor().update(match.group(1), request.campaign)

    def _editor_systems(self, _match: re.Match[str]) -> tuple[int, Payload]:
        return 200, self._editor().systems()

    def _editor_system(self, match: re.Match[str]) -> tuple[int, Payload]:
        return 200, self._editor().system(match.group(1))

    def _editor_preview(self, _match: re.Match[str]) -> tuple[int, Payload]:
        request = self._read_json(ValidateRequest, limit=MAX_EDITOR_BODY)
        return 200, self._editor().preview(request.campaign)

    ROUTES: tuple[Route, ...] = (
        ("GET", re.compile(r"^/campaigns$"), _campaigns),
        ("POST", re.compile(r"^/tables$"), _create_table),
        ("GET", re.compile(r"^/tables/([^/]+)$"), _get_table),
        ("GET", re.compile(r"^/tables/([^/]+)/campaign$"), _get_campaign),
        ("GET", re.compile(r"^/tables/([^/]+)/rules$"), _get_rules),
        ("POST", re.compile(r"^/tables/([^/]+)/preview$"), _preview_invite),
        ("POST", re.compile(r"^/tables/([^/]+)/players$"), _join_table),
        ("POST", re.compile(r"^/tables/([^/]+)/commands$"), _command),
        ("POST", re.compile(r"^/tables/([^/]+)/lifecycle$"), _lifecycle),
        ("POST", re.compile(r"^/tables/([^/]+)/say$"), _say),
        ("POST", re.compile(r"^/tables/([^/]+)/copilot$"), _copilot),
        ("GET", re.compile(r"^/tables/([^/]+)/events$"), _get_events),
        ("GET", re.compile(r"^/editor/campaigns$"), _editor_campaigns),
        ("POST", re.compile(r"^/editor/campaigns$"), _editor_create),
        ("GET", re.compile(r"^/editor/campaigns/([^/]+)$"), _editor_get),
        ("PUT", re.compile(r"^/editor/campaigns/([^/]+)$"), _editor_update),
        ("POST", re.compile(r"^/editor/validate$"), _editor_validate),
        ("POST", re.compile(r"^/editor/preview$"), _editor_preview),
        ("GET", re.compile(r"^/editor/systems$"), _editor_systems),
        ("GET", re.compile(r"^/editor/systems/([^/]+)$"), _editor_system),
    )

    # --- despacho ----------------------------------------------------------------

    def do_GET(self) -> None:
        """Trata GET: rota da API ou arquivo do app."""
        self._dispatch("GET")

    def do_POST(self) -> None:
        """Trata POST: rota da API; corpo sempre JSON."""
        self._dispatch("POST")

    # Métodos sem rota respondem em JSON (405/404) em vez do HTML da stdlib.
    def do_PUT(self) -> None:
        """405 em JSON: a API não tem rota PUT."""
        self._dispatch("PUT")

    def do_PATCH(self) -> None:
        """405 em JSON: a API não tem rota PATCH."""
        self._dispatch("PATCH")

    def do_DELETE(self) -> None:
        """405 em JSON: a API não tem rota DELETE."""
        self._dispatch("DELETE")

    def do_HEAD(self) -> None:
        """Trata HEAD: só arquivos do app respondem, sem corpo."""
        self._dispatch("HEAD")

    def do_OPTIONS(self) -> None:
        """405 em JSON: não há CORS, porque o app vem da mesma origem."""
        self._dispatch("OPTIONS")

    def _dispatch(self, method: str) -> None:
        path = urlsplit(self.path).path
        self._body_read = False
        try:
            self._guard_editor(method, path)
            found_route = None
            path_known = False
            for route_method, pattern, handler in self.ROUTES:
                match = pattern.match(path)
                if match is None:
                    continue
                path_known = True  # a rota existe, talvez para outro método
                if route_method == method:
                    found_route = (handler, match)
                    break
            if path_known and found_route is None:
                raise ApiFailure(405, "method_not_allowed", f"{method} não vale para {path}")
            if found_route is not None:
                handler, match = found_route
                status, payload = handler(self, match)
            else:
                # A API vem sempre antes: só o que nenhuma rota de API reconhece pode ser arquivo.
                site = self.server.static
                raw = self.path.split("?", 1)[
                    0
                ]  # sem urlsplit: ``//x`` não vira "host x" e some o ``//``
                found = site.lookup(raw) if site and method in ("GET", "HEAD") else None
                if found is None:
                    raise ApiFailure(404, "not_found", f"rota desconhecida: {path}")
                self._send_file(found, head_only=method == "HEAD")
                return
        except ApiFailure as exc:
            if method not in ("GET", "HEAD") and not self._body_read:
                self.close_connection = (
                    True  # recusou sem ler o corpo: os bytes não podem virar outra requisição
                )
            self._send_error(exc.status, exc.code, exc.message)
            return
        except Exception:  # noqa: BLE001 — fronteira do handler HTTP: 500 genérico, traceback no stderr
            traceback.print_exc(file=sys.stderr)
            self._send_error(500, "internal", "erro interno")
            return
        self._send(status, payload)

    def _guard_editor(self, method: str, path: str) -> None:
        """Sem ``--editor``, ``/editor/*`` não existe; com ele, só pedidos de dentro desta máquina (rule 05, item 25).

        Vale para toda requisição, não só ``/editor/*``: ``Host`` precisa ser um nome local com a porta do
        servidor (DNS rebinding) e, num pedido que muda algo, o ``Origin`` que vier precisa ser o próprio
        servidor (CSRF). Um front servido de outra origem (dev server) precisa de proxy.
        """
        editor = self.server.editor
        if editor is None:
            if path == "/editor" or path.startswith("/editor/"):
                raise ApiFailure(404, "not_found", f"rota desconhecida: {path}")
            return
        host = self.headers.get("Host")
        refused: ApiFailure | None = None
        if not host_allowed(host, self.server.server_address[1]):
            refused = ApiFailure(403, "host_not_allowed", "o editor só responde em localhost")
        elif method not in ("GET", "HEAD") and not origin_allowed(self.headers.get("Origin"), host):
            refused = ApiFailure(403, "origin_not_allowed", "origem não permitida")
        if refused is not None:
            self.close_connection = (
                True  # o corpo não foi lido: fecha, ou os bytes viram a próxima requisição
            )
            raise refused

    # --- leitura -----------------------------------------------------------------

    def _query_int(self, name: str, *, default: int, max_digits: int = 9) -> int:
        values = parse_qs(urlsplit(self.path).query).get(name)
        if not values:
            return default
        raw = values[0]
        if len(values) > 1 or not (raw.isascii() and raw.isdigit()) or len(raw) > max_digits:
            raise ApiFailure(400, "bad_request", f"'{name}' precisa ser um inteiro não negativo")
        return int(raw)

    def _token(self) -> str | None:
        # self.headers.get é case-insensitive (email.message.Message), como manda o HTTP.
        return bearer_token(self.headers.get("Authorization"))

    def _read_json(self, model: type[M], *, limit: int = MAX_BODY) -> M:
        try:
            length = self._declared_length(limit)
        except ApiFailure:
            # Corpo recusado sem ler: fecha a conexão, ou os bytes viram a próxima requisição.
            self.close_connection = True
            raise
        try:
            body = self.rfile.read(length)
            self._body_read = True
        except (TimeoutError, ConnectionError):
            # Cliente mandou menos do que anunciou e sumiu: nada a responder, só fechar.
            self.close_connection = True
            raise ApiFailure(408, "request_timeout", "corpo incompleto") from None
        try:
            return model.model_validate_json(body)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc']) or 'corpo'}: {e['msg']}" for e in exc.errors()
            )
            raise ApiFailure(400, "bad_request", f"corpo inválido: {problems}") from None

    def _declared_length(self, limit: int) -> int:
        if self.headers.get("Transfer-Encoding"):
            raise ApiFailure(
                400, "bad_request", "Transfer-Encoding não é aceito; envie Content-Length"
            )
        lengths = self.headers.get_all("Content-Length") or []
        if len(lengths) > 1:
            raise ApiFailure(400, "bad_request", "Content-Length repetido")
        raw_length = lengths[0].strip() if lengths else ""
        # isascii: str.isdigit aceita dígitos Unicode que int() recusa.
        if not (raw_length.isascii() and raw_length.isdigit()):
            raise ApiFailure(411, "length_required", "Content-Length ausente ou inválido")
        length = int(raw_length)
        if length > limit:
            raise ApiFailure(413, "payload_too_large", f"corpo acima de {limit} bytes")
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type != JSON:
            raise ApiFailure(415, "unsupported_media_type", f"Content-Type precisa ser {JSON}")
        return length

    # --- escrita -----------------------------------------------------------------

    def _send(self, status: int, payload: Payload) -> None:
        if isinstance(payload, BaseModel):
            text = payload.model_dump_json()
        else:
            text = json.dumps([m.model_dump(mode="json") for m in payload], ensure_ascii=False)
        self._send_bytes(status, text.encode("utf-8"))

    def _send_error(self, status: int, code: str, message: str) -> None:
        body = ErrorResponse(error=ApiError(code=code, message=message))
        self._send_bytes(status, body.model_dump_json().encode("utf-8"))

    def _send_bytes(self, status: int, body: bytes) -> None:
        self._respond(
            status,
            body,
            {
                "Content-Type": f"{JSON}; charset=utf-8",
                "Cache-Control": "no-store",
                "X-Content-Type-Options": SECURITY_HEADERS["X-Content-Type-Options"],
            },
        )

    def _send_file(self, found: StaticFile, *, head_only: bool) -> None:
        body = b""
        if not head_only:  # HEAD só precisa do tamanho que o lookup já mediu
            try:
                with found.path.open("rb") as handle:
                    body = handle.read(MAX_STATIC_BYTES + 1)  # o teto vale para o que foi lido
            except OSError:  # sumiu entre o lookup e a leitura
                raise ApiFailure(404, "not_found", "arquivo não encontrado") from None
            if len(body) > MAX_STATIC_BYTES:
                raise ApiFailure(404, "not_found", "arquivo não encontrado")
        self._respond(
            200,
            body,
            {
                "Content-Type": found.content_type,
                "Cache-Control": found.cache_control,
                **SECURITY_HEADERS,
            },
            head_only=head_only,
            length=found.size if head_only else None,
        )

    def _respond(
        self,
        status: int,
        body: bytes,
        headers: dict[str, str],
        *,
        head_only: bool = False,
        length: int | None = None,
    ) -> None:
        # HEAD leva os mesmos cabeçalhos (Content-Length inclusive) e nenhum corpo.
        head_only = head_only or self.command == "HEAD"
        try:
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body) if length is None else length))
            if self.close_connection:
                self.send_header("Connection", "close")
            self.end_headers()
            if not head_only:
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # O cliente foi embora no meio da resposta: nada a fazer além de não derrubar a thread.
            self.close_connection = True

    # --- log ---------------------------------------------------------------------

    def log_request(self, code: int | str = "-", _size: int | str = "-") -> None:
        # Só método, rota e status: nunca cabeçalho, corpo nem query string.
        """Registra só método, rota e status: nunca cabeçalho, corpo nem query string."""
        self.log_message('"%s %s" %s', self.command, urlsplit(self.path).path, code)

    def log_message(self, format: str, *args: object) -> None:
        """Escreve o registro no erro padrão."""
        sys.stderr.write(f"{self.address_string()} {format % args}\n")


def make_server(
    host: str,
    port: int,
    service: TableService,
    static: StaticSite | None = None,
    editor: EditorService | None = None,
) -> ApiServer:
    """Cria o servidor HTTP, sem iniciá-lo."""
    return ApiServer((host, port), service, static, editor)
