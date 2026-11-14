from devaneio.engine import end_turn, initial_state


def test_end_turn_increments_and_logs(campaign, rules):
    state = initial_state(campaign, rules, 1)
    after = end_turn(state)
    assert state.turn == 0
    assert state.events == []
    assert after.turn == 1
    assert [(e.kind, e.turn, e.text) for e in after.events] == [("turn_end", 0, "Fim do turno 0")]
    assert end_turn(after).turn == 2
