"""Chat da mesa: enviar, ler, limites, fases, long-poll e persistência."""

import threading
import time
from itertools import count

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from conftest import CAMPAIGN_PATH, make_storage
from devaneio.server import ApiFailure, Catalog, TableService
from devaneio.server.models import (
    ChatRequest,
    CreateTableRequest,
    JoinRequest,
    LifecycleRequest,
)

TOKENS = count(1)


class Clock:
    """Relógio do servidor que o teste move à mão."""

    def __init__(self):
        self.now = 1_000.0

    def __call__(self):
        return self.now


class Room:
    """Uma mesa na sala de espera com o anfitrião Ana, e o relógio na mão do teste."""

    def __init__(self, tmp_path):
        self.clock = Clock()
        self.storage = make_storage(tmp_path / "mesas", max_tables=10, clock=self.clock)
        self.service = TableService(
            Catalog(CAMPAIGN_PATH.parent),
            self.storage,
            token_source=lambda: f"token-{next(TOKENS)}",
            invite_source=lambda: "convite",
            clock=self.clock,
        )
        created = self.service.create_table(
            CreateTableRequest(campaign_id="sombra-do-vale", host_name="Ana", seed=7)
        )
        self.id, self.host = created.table_id, created.host_token

    def join(self, name):
        return self.service.join_table(self.id, JoinRequest(invite_code="convite", name=name)).token

    def say(self, token, text):
        return self.service.post_chat(self.id, token, ChatRequest(text=text))

    def later(self, seconds=2.0):
        self.clock.now += seconds


@pytest.fixture
def room(tmp_path):
    return Room(tmp_path)


def test_a_mensagem_chega_a_todos_com_nome_e_papel(room):
    bruno = room.join("Bruno")
    first = room.say(room.host, "vamos pelas ruínas?")
    room.later()
    room.say(bruno, "bora")
    for token in (room.host, bruno):
        chat = room.service.get_chat(room.id, token, 0)
        assert [(m.seq, m.name, m.role, m.text) for m in chat.messages] == [
            (1, "Ana", "host", "vamos pelas ruínas?"),
            (2, "Bruno", "player", "bora"),
        ]
        assert chat.chat_seq == 2
    assert first.at == 1_000.0


def test_since_devolve_so_as_novas_e_a_leitura_vazia_mantem_a_posicao(room):
    room.say(room.host, "um")
    room.later()
    room.say(room.host, "dois")
    chat = room.service.get_chat(room.id, room.host, 1)
    assert [m.text for m in chat.messages] == ["dois"]
    empty = room.service.get_chat(room.id, room.host, 2)
    assert empty.messages == []
    assert empty.chat_seq == 2


def test_sem_token_ou_com_token_errado_recusa_e_nada_e_gravado(room):
    for token in (None, "invalido"):
        with pytest.raises(ApiFailure) as info:
            room.say(token, "oi")
        assert info.value.status == 401
        with pytest.raises(ApiFailure):
            room.service.get_chat(room.id, token, 0)
    assert room.service.get_chat(room.id, room.host, 0).messages == []


def test_mesa_inexistente_e_404(room):
    with pytest.raises(ApiFailure) as info:
        room.service.post_chat("0" * 16, room.host, ChatRequest(text="oi"))
    assert info.value.status == 404


def test_uma_mensagem_por_segundo_por_jogador(room):
    bruno = room.join("Bruno")
    room.say(room.host, "um")
    with pytest.raises(ApiFailure) as info:
        room.say(room.host, "dois")
    assert (info.value.status, info.value.code) == (429, "chat_rate_limited")
    room.say(bruno, "outro jogador não espera")  # o intervalo é por jogador
    room.later(1.5)
    room.say(room.host, "agora pode")
    assert [m.text for m in room.service.get_chat(room.id, room.host, 0).messages] == [
        "um",
        "outro jogador não espera",
        "agora pode",
    ]


def test_mesa_encerrada_e_so_leitura(room):
    room.say(room.host, "antes")
    room.later()
    room.service.set_phase(room.id, room.host, LifecycleRequest(action="end", revision=0))
    with pytest.raises(ApiFailure) as info:
        room.say(room.host, "depois")
    assert (info.value.status, info.value.code) == (409, "ended")
    assert [m.text for m in room.service.get_chat(room.id, room.host, 0).messages] == ["antes"]


def test_texto_invalido_e_recusado_pelo_modelo():
    for bad in ("", "   ", "duas\nlinhas", "esc\x1b[31m", "zero\u200bwidth", "x" * 501):
        with pytest.raises(ValidationError):
            ChatRequest(text=bad)
    assert ChatRequest(text="  oi  ").text == "oi"
    assert ChatRequest(text="x" * 500).text == "x" * 500


def test_marcacao_nao_e_escapada_no_servidor(room):
    room.say(room.host, "<img src=x onerror=alert(1)>")
    assert room.service.get_chat(room.id, room.host, 0).messages[0].text == (
        "<img src=x onerror=alert(1)>"
    )


def test_o_historico_guarda_so_as_ultimas_500_e_le_100_por_vez(room):
    for n in range(1, 511):
        room.say(room.host, f"m{n}")
        room.later()
    everything = room.service.get_chat(room.id, room.host, 0)
    assert len(everything.messages) == 100
    assert everything.chat_seq == 510
    assert everything.messages[0].seq == 411
    assert everything.messages[-1].seq == 510
    assert room.service.get_chat(room.id, room.host, 10).messages[0].seq == 411
    old = room.storage.database.read(
        lambda s: s.execute(text("SELECT MIN(seq) FROM chat_messages")).scalar_one()
    )
    assert old == 11  # as 10 mais antigas saíram na gravação


def test_as_mesas_nao_se_misturam(room, tmp_path):
    other = Room(tmp_path / "outra")
    room.say(room.host, "só da primeira")
    assert other.service.get_chat(other.id, other.host, 0).messages == []


def _wait_in_thread(room, token, **query):
    """Começa um long-poll numa thread e só devolve quando a espera está de fato armada no servidor."""
    results = []
    thread = threading.Thread(
        target=lambda: results.append(room.service.get_events(room.id, token, 0, wait=5, **query))
    )
    thread.start()
    for _ in range(500):
        if room.storage.waiting(room.id) == 1:
            return thread, results
        time.sleep(0.01)
    raise AssertionError("a espera do long-poll não começou")


def test_o_chat_acorda_o_long_poll_que_ja_estava_esperando(room):
    room.say(room.host, "antiga")
    bruno = room.join("Bruno")
    seen = room.service.get_events(room.id, bruno, 0, wait=0)
    assert [m.text for m in seen.chat] == ["antiga"]
    assert seen.chat_seq == 1

    thread, results = _wait_in_thread(room, bruno, since_chat=seen.chat_seq)
    room.later()
    room.say(room.host, "nova")
    thread.join(timeout=5)
    assert not thread.is_alive()
    (view,) = results
    assert [m.text for m in view.chat] == ["nova"]
    assert view.chat_seq == 2


def test_sem_since_chat_o_historico_nao_acorda_a_espera_so_a_mensagem_nova(room):
    room.say(room.host, "antiga")
    bruno = room.join("Bruno")
    thread, results = _wait_in_thread(room, bruno)  # sem since_chat: a "antiga" não conta
    assert thread.is_alive()  # continua esperando, mesmo com histórico no banco
    room.later()
    room.say(room.host, "nova")
    thread.join(timeout=5)
    (view,) = results
    assert [m.text for m in view.chat] == ["nova"]


def test_since_chat_zero_explicito_conta_e_nao_perde_a_primeira_mensagem(room):
    room.say(room.host, "a primeira, entre duas chamadas de um chat que estava vazio")
    view = room.service.get_events(room.id, room.host, 0, wait=1, since_chat=0)
    assert [m.seq for m in view.chat] == [1]


def test_apagar_a_mesa_de_vez_leva_o_chat_junto(room):
    room.say(room.host, "oi")
    room.storage.archive(room.id)
    assert room.storage.delete(room.id)
    count_rows = room.storage.database.read(
        lambda s: s.execute(text("SELECT COUNT(*) FROM chat_messages")).scalar_one()
    )
    assert count_rows == 0
