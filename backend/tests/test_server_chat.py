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
        self.ids = {"Ana": "p1"}

    def join(self, name):
        joined = self.service.join_table(self.id, JoinRequest(invite_code="convite", name=name))
        self.ids[name] = joined.player_id
        return joined.token

    def say(self, token, text, to=None):
        return self.service.post_chat(self.id, token, ChatRequest(text=text, to=to))

    def texts(self, token, since=0):
        return [m.text for m in self.service.get_chat(self.id, token, since).messages]

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


class Trio:
    """Ana (anfitriã), Bruno e Carla, com um sussurro de Bruno para Carla já enviado."""

    def __init__(self, tmp_path):
        self.room = Room(tmp_path)
        self.ana = self.room.host
        self.bruno = self.room.join("Bruno")
        self.carla = self.room.join("Carla")
        self.ids = self.room.ids


@pytest.fixture
def trio(tmp_path):
    return Trio(tmp_path)


def test_o_sussurro_so_e_visto_por_quem_enviou_e_por_quem_recebeu(trio):
    room = trio.room
    sent = room.say(trio.bruno, "o ferreiro mente", to=trio.ids["Carla"])
    assert (sent.to, sent.to_name) == (trio.ids["Carla"], "Carla")
    assert room.texts(trio.bruno) == ["o ferreiro mente"]
    assert room.texts(trio.carla) == ["o ferreiro mente"]
    assert room.texts(trio.ana) == []  # nem o anfitrião lê o que não é dele


def test_a_mensagem_publica_e_o_sussurro_convivem_na_mesma_conversa(trio):
    room = trio.room
    room.say(trio.ana, "bom dia a todos")
    room.later()
    room.say(trio.bruno, "só para você", to=trio.ids["Carla"])
    room.later()
    room.say(trio.carla, "entendi", to=trio.ids["Bruno"])
    assert room.texts(trio.ana) == ["bom dia a todos"]
    assert room.texts(trio.bruno) == ["bom dia a todos", "só para você", "entendi"]
    assert room.texts(trio.carla) == ["bom dia a todos", "só para você", "entendi"]


def test_o_cursor_sobe_mesmo_com_sussurro_alheio_e_nada_dele_vaza(trio):
    room = trio.room
    room.say(trio.bruno, "segredo", to=trio.ids["Carla"])
    chat = room.service.get_chat(room.id, trio.ana, 0)
    assert chat.messages == []
    assert chat.chat_seq == 1  # a posição é da mesa, o conteúdo não
    assert "segredo" not in chat.model_dump_json()


def test_o_long_poll_filtra_o_sussurro_e_acorda_so_o_destinatario(trio):
    room = trio.room
    room.say(trio.bruno, "só para a Carla", to=trio.ids["Carla"])
    seen = room.service.get_events(room.id, trio.carla, 0, wait=0)
    assert [m.text for m in seen.chat] == ["só para a Carla"]
    assert room.service.get_events(room.id, trio.ana, 0, wait=0).chat == []
    assert room.service.get_events(room.id, trio.bruno, 0, wait=0).chat == seen.chat


def test_um_sussurro_novo_chega_ao_destinatario_que_ja_esperava(trio):
    room = trio.room
    thread, results = _wait_in_thread(room, trio.carla, since_chat=0)
    room.say(trio.bruno, "psiu", to=trio.ids["Carla"])
    thread.join(timeout=5)
    (view,) = results
    assert [m.text for m in view.chat] == ["psiu"]


def test_sussurro_alheio_nao_entrega_nada_a_quem_esperava_e_a_espera_continua(trio):
    room = trio.room
    thread, results = _wait_in_thread(room, trio.ana, since_chat=0)
    room.say(trio.bruno, "entre nós", to=trio.ids["Carla"])
    time.sleep(0.2)
    assert thread.is_alive()  # acordou, nada para ela, voltou a esperar
    room.later()
    room.say(trio.carla, "para todos")
    thread.join(timeout=5)
    (view,) = results
    assert [m.text for m in view.chat] == ["para todos"]


def test_o_limite_de_100_conta_so_o_que_a_pessoa_pode_ver(trio):
    room = trio.room
    for n in range(3):
        room.say(trio.bruno, f"privado {n}", to=trio.ids["Carla"])
        room.later()
    room.say(trio.bruno, "público")
    assert room.texts(trio.ana) == ["público"]


@pytest.mark.parametrize("target", ["eu", "p99", "inexistente"])
def test_destinatario_invalido_e_recusado_e_nada_e_gravado(trio, target):
    room = trio.room
    to = trio.ids["Bruno"] if target == "eu" else target
    with pytest.raises(ApiFailure) as info:
        room.say(trio.bruno, "oi", to=to)
    assert (info.value.status, info.value.code) == (422, "bad_recipient")
    assert room.texts(trio.bruno) == []


def test_da_para_sussurrar_para_o_anfitriao_e_ele_responde(trio):
    room = trio.room
    room.say(trio.bruno, "posso pedir uma dica?", to=trio.ids["Ana"])
    room.later()
    room.say(trio.ana, "olhe o altar", to=trio.ids["Bruno"])
    assert room.texts(trio.ana) == ["posso pedir uma dica?", "olhe o altar"]
    assert room.texts(trio.bruno) == ["posso pedir uma dica?", "olhe o altar"]
    assert room.texts(trio.carla) == []


def test_o_nome_do_destinatario_e_resolvido_na_hora_de_mostrar(trio):
    room = trio.room
    room.say(trio.bruno, "oi", to=trio.ids["Carla"])
    (message,) = room.service.get_chat(room.id, trio.bruno, 0).messages
    assert message.to_name == "Carla"
