"""Dublês para testar o LLM sem rede: um servidor HTTP local no formato OpenAI e um
cliente roteirizado."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeLlmServer:
    """``respond(body) -> (status, payload)``: str vira ``choices[0].message.content``;
    dict/list é o corpo JSON cru; bytes é o corpo cru. Guarda cada requisição em ``requests``."""

    def __init__(self, respond):
        self.respond = respond
        self.requests: list[dict] = []

    def __enter__(self) -> FakeLlmServer:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                outer.requests.append(
                    {
                        "path": self.path,
                        "authorization": self.headers.get("Authorization"),
                        "json": body,
                    }
                )
                status, payload = outer.respond(body)
                if isinstance(payload, str):
                    payload = {"choices": [{"message": {"role": "assistant", "content": payload}}]}
                data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"
        return self

    def __exit__(self, *exc) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class ScriptedClient:
    """Cliente falso: devolve respostas em ordem; uma Exception na fila é levantada."""

    description = "cliente falso"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def complete(self, messages, *, json_mode=False, temperature=None):
        self.calls.append(
            {
                "messages": [dict(m) for m in messages],
                "json_mode": json_mode,
                "temperature": temperature,
            }
        )
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
