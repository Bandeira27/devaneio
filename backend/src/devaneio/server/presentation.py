"""Exibição em memória de uma mesa: a narração do LLM por evento e o mural de falas.

Nada daqui vai ao arquivo nem ao estado (o LLM só propõe) e tudo some ao reiniciar o
servidor. Fica fora do ``Storage``, que cuida de caminho, lock, versão e vagas.
"""

from __future__ import annotations

import threading

from .models import TalkView

MAX_NARRATIONS = 200  # narrações guardadas por mesa; as mais antigas saem primeiro
MAX_TALK = 50  # falas guardadas por mesa; as mais antigas saem primeiro


class Presentation:
    """O que é só exibição e fica em memória: narrações do LLM e falas do mestre."""

    def __init__(self, talk_seq: int) -> None:
        # Os números das falas partem do relógio, para continuar acima dos já vistos após um reinício.
        self._talk_seq = talk_seq
        self._narrations: dict[int, str] = {}
        self._talk: list[TalkView] = []
        self._lock = threading.Lock()

    def narrations(self) -> dict[int, str]:
        """Parágrafo de narração do LLM por índice de evento; sem ele vale a gramática."""
        with self._lock:
            return dict(self._narrations)

    def store_narrations(self, narrations: dict[int, str]) -> None:
        """Guarda as narrações novas, descartando as mais antigas acima do limite."""
        with self._lock:
            self._narrations.update(narrations)
            while len(self._narrations) > MAX_NARRATIONS:
                del self._narrations[next(iter(self._narrations))]  # ordem de inserção

    def add_talk(self, *, after: int, to: str, text: str) -> TalkView:
        """Acrescenta uma fala do mestre ou de um NPC e devolve com o número dela."""
        with self._lock:
            self._talk_seq += 1
            entry = TalkView(seq=self._talk_seq, after=after, to=to, text=text)
            self._talk.append(entry)
            del self._talk[:-MAX_TALK]
            return entry

    def talk_since(self, since: int) -> tuple[list[TalkView], int]:
        """As falas com ``seq`` maior que ``since`` e o último ``seq`` da mesa."""
        with self._lock:
            return [e for e in self._talk if e.seq > since], self._talk_seq
