"""Texto livre pela mesa: o LLM do anfitrião PROPÕE ações, cada uma passa pela política do
jogador e pelo motor, e a proposta inteira gasta uma ação principal do personagem.

Três fases: (1) sob o lock da mesa, confere tudo e para se algo recusa; (2) SEM o lock,
chama o LLM (pode levar minutos e não pode travar os comandos); (3) sob o lock de novo,
grava só se a mesa continua como era, senão ``409`` e a tentativa se perde.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from devaneio.engine import game_status
from devaneio.game import (
    CommandError,
    GameOverError,
    LlmUnavailableError,
    Player,
    Session,
    TableMeta,
    connect_llm,
    narrate_batch,
    parse_line,
    run_freeform,
    save_game,
)
from devaneio.llm import ChatClient, LlmConfig

from . import policy
from .errors import ApiFailure
from .models import SayRequest, SayResult
from .storage import Storage
from .turns import (
    authenticate,
    authorize_proposal,
    check_say,
    close_turn_if_all_acted,
    events_view,
    hidden_events,
    speaker,
)


class SayDesk:
    def __init__(self, storage: Storage, llm: LlmConfig, load: Callable[[Path], Session]) -> None:
        self._storage = storage
        self._llm = llm
        self._load = load  # carrega a partida; levanta o erro interno se ela estiver ilegível

    def run(self, table_id: str, path: Path, token: str, request: SayRequest) -> SayResult:
        storage = self._storage
        with storage.lock(table_id):  # fase 1
            session = self._load(path)
            table, _, player = authenticate(session, token)
            who, text = speaker(session.state, player, request.text)
            check_say(table, session.state, who, request.revision)
        if not storage.enter_say(table_id):
            raise ApiFailure(409, "say_busy", "já há uma ação de texto livre em andamento")
        try:
            return self._with_llm(table_id, path, (session, table, player, who, text))
        finally:
            storage.leave_say(table_id)

    def _with_llm(
        self,
        table_id: str,
        path: Path,
        sent: tuple[Session, TableMeta, Player, str, str],
    ) -> SayResult:
        session, table, player, who, text = sent
        client = connect_llm(self._llm)
        revision = len(session.state.events)
        try:  # fase 2, sem lock
            freeform = run_freeform(
                replace(session, llm=client),
                text,
                actor=who,
                allow=lambda working, line: authorize_proposal(player, working, line),
            )
        except GameOverError as exc:
            raise ApiFailure(409, "game_over", str(exc)) from None
        except LlmUnavailableError as exc:
            print(f"llm: {exc}", file=sys.stderr)  # o detalhe fica com quem roda o servidor
            raise ApiFailure(
                502, "llm_unavailable", "o servidor de LLM não respondeu direito"
            ) from None
        except CommandError as exc:
            raise ApiFailure(422, "command_refused", str(exc)) from None

        new_session, new_table, turn_ended = freeform.session, table, False
        if any(policy.classify(parse_line(c)[1]) == "action" for c in freeform.commands):
            new_table = table.model_copy(update={"acted": {**table.acted, who: session.state.turn}})
            new_session, _, turn_ended = close_turn_if_all_acted(new_session, new_table, "")
        fresh_events = new_session.state.events[revision:]
        prose = self._narration(client, new_session, revision) if fresh_events else {}

        with self._storage.lock(table_id):  # fase 3
            current = self._load(path)
            if len(current.state.events) != revision or current.table != table:
                raise ApiFailure(
                    409, "stale_revision", "a mesa mudou enquanto o mestre pensava: tente de novo"
                )
            if fresh_events:
                save_game(replace(new_session, table=new_table))
                self._storage.store_prose(table_id, prose)
                self._storage.announce_change(table_id)
        shown = events_view(new_session, revision, self._storage.prose(table_id), role=player.role)
        return SayResult(
            revision=len(new_session.state.events),
            events=shown,
            text="\n".join(e.text for e in shown),
            status=game_status(new_session.state),
            turn_ended=turn_ended,
            say=freeform.say,
            commands=list(freeform.commands),
        )

    @staticmethod
    def _narration(client: ChatClient, session: Session, start: int) -> dict[int, str]:
        """Um parágrafo do LLM para o lote de eventos novos que os JOGADORES veem, no índice do
        primeiro deles: o parágrafo é igual para todos, então não pode citar o que só o
        anfitrião vê (evento sobre NPC escondido). Se o LLM falhar, nada: ``narration`` fica
        ``None`` e vale a prosa da gramática."""
        state = session.state
        hidden = hidden_events(state, session.campaign)
        visible = [i for i in range(start, len(state.events)) if i not in hidden]
        if not visible:
            return {}
        paragraph, note = narrate_batch(
            client, session.campaign, state, [state.events[i].text for i in visible]
        )
        if paragraph is None:
            print(f"llm: {note}", file=sys.stderr)
            return {}
        return {visible[0]: paragraph}
