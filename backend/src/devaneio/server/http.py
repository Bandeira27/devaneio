"""Adaptador HTTP sobre ``TableService``: roteamento, JSON e mapeamento de erros.

Só biblioteca padrão (``http.server``). O handler é a fronteira de execução: qualquer
exceção não prevista vira ``500`` genérico com traceback no stderr, nunca no corpo.
"""

from __future__ import annotations

import json
import re
import sys
import traceback
from collections.abc import Callable, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TypeAlias, TypeVar
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, ValidationError

from .app import ApiFailure, TableService
from .auth import bearer_token
from .models import ApiError, CommandRequest, CreateTableRequest, ErrorResponse, JoinRequest

MAX_BODY = 64 * 1024
MAX_WAIT = 30  # segundos de long-poll
JSON = "application/json"
M = TypeVar("M", bound=BaseModel)

Payload: TypeAlias = BaseModel | Sequence[BaseModel]
Route: TypeAlias = tuple[
    str, re.Pattern[str], Callable[["Handler", re.Match[str]], "tuple[int, Payload]"]
]


class ApiServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], service: TableService) -> None:
        super().__init__(address, Handler)
        self.service = service


class Handler(BaseHTTPRequestHandler):
    server: ApiServer
    server_version = "devaneio"
    sys_version = ""
    timeout = 15  # segundos sem dados na conexão: cliente que some não prende a thread
    protocol_version = "HTTP/1.1"

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

    def _join_table(self, match: re.Match[str]) -> tuple[int, Payload]:
        request = self._read_json(JoinRequest)
        return 201, self.server.service.join_table(match.group(1), request)

    def _command(self, match: re.Match[str]) -> tuple[int, Payload]:
        request = self._read_json(CommandRequest)
        return 200, self.server.service.run_command(match.group(1), self._token(), request)

    def _get_events(self, match: re.Match[str]) -> tuple[int, Payload]:
        since = self._query_int("since", default=0)
        wait = self._query_int("wait", default=0)
        if wait > MAX_WAIT:
            raise ApiFailure(400, "bad_request", f"'wait' vai de 0 a {MAX_WAIT} segundos")
        return 200, self.server.service.get_events(match.group(1), self._token(), since, wait)

    ROUTES: tuple[Route, ...] = (
        ("GET", re.compile(r"^/campaigns$"), _campaigns),
        ("POST", re.compile(r"^/tables$"), _create_table),
        ("GET", re.compile(r"^/tables/([^/]+)$"), _get_table),
        ("GET", re.compile(r"^/tables/([^/]+)/campaign$"), _get_campaign),
        ("POST", re.compile(r"^/tables/([^/]+)/players$"), _join_table),
        ("POST", re.compile(r"^/tables/([^/]+)/commands$"), _command),
        ("GET", re.compile(r"^/tables/([^/]+)/events$"), _get_events),
    )

    # --- despacho ----------------------------------------------------------------

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    # Métodos sem rota respondem em JSON (405/404) em vez do HTML da stdlib.
    def do_PUT(self) -> None:
        self._dispatch("PUT")

    def do_PATCH(self) -> None:
        self._dispatch("PATCH")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def do_HEAD(self) -> None:
        self._dispatch("HEAD")

    def do_OPTIONS(self) -> None:
        self._dispatch("OPTIONS")

    def _dispatch(self, method: str) -> None:
        path = urlsplit(self.path).path
        try:
            for route_method, pattern, handler in self.ROUTES:
                match = pattern.match(path)
                if match is None:
                    continue
                if route_method != method:
                    raise ApiFailure(405, "method_not_allowed", f"{method} não vale para {path}")
                status, payload = handler(self, match)
                break
            else:
                raise ApiFailure(404, "not_found", f"rota desconhecida: {path}")
        except ApiFailure as exc:
            self._send_error(exc.status, exc.code, exc.message)
            return
        except Exception:  # noqa: BLE001 — fronteira do handler HTTP: 500 genérico, traceback no stderr
            traceback.print_exc(file=sys.stderr)
            self._send_error(500, "internal", "erro interno")
            return
        self._send(status, payload)

    # --- leitura -----------------------------------------------------------------

    def _query_int(self, name: str, *, default: int) -> int:
        values = parse_qs(urlsplit(self.path).query).get(name)
        if not values:
            return default
        raw = values[0]
        if len(values) > 1 or not (raw.isascii() and raw.isdigit()) or len(raw) > 9:
            raise ApiFailure(400, "bad_request", f"'{name}' precisa ser um inteiro não negativo")
        return int(raw)

    def _token(self) -> str | None:
        # self.headers.get é case-insensitive (email.message.Message), como manda o HTTP.
        return bearer_token(self.headers.get("Authorization"))

    def _read_json(self, model: type[M]) -> M:
        try:
            length = self._declared_length()
        except ApiFailure:
            # Corpo recusado sem ser lido: fechar a conexão, senão os bytes dele viram a
            # próxima requisição do keep-alive (desync de Content-Length).
            self.close_connection = True
            raise
        try:
            body = self.rfile.read(length)
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

    def _declared_length(self) -> int:
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
        if length > MAX_BODY:
            raise ApiFailure(413, "payload_too_large", f"corpo acima de {MAX_BODY} bytes")
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
        try:
            self.send_response(status)
            self.send_header("Content-Type", f"{JSON}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if self.close_connection:
                self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # O cliente foi embora no meio da resposta: nada a fazer além de não derrubar a thread.
            self.close_connection = True

    # --- log ---------------------------------------------------------------------

    def log_request(self, code: int | str = "-", _size: int | str = "-") -> None:
        # Só método, rota e status: nunca cabeçalho, corpo nem query string.
        self.log_message('"%s %s" %s', self.command, urlsplit(self.path).path, code)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(f"{self.address_string()} {format % args}\n")


def make_server(host: str, port: int, service: TableService) -> ApiServer:
    return ApiServer((host, port), service)
