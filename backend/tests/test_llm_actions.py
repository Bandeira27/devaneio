import json

import pytest

from devaneio.llm import (
    EXAMPLE_PROPOSAL,
    AttackAction,
    CheckAction,
    MoveAction,
    ProposalError,
    RestAction,
    parse_proposal,
    to_command,
)


def test_example_proposal_is_valid():
    proposal = parse_proposal(json.dumps(EXAMPLE_PROPOSAL))
    assert [a.kind for a in proposal.actions] == ["check", "move"]
    assert proposal.say.startswith("Você some")


def test_all_action_kinds_and_commands():
    raw = json.dumps(
        {
            "actions": [
                {"kind": "check", "skill": "furtividade", "difficulty": "dificil", "modifier": "vantagem"},
                {"kind": "attack", "weapon": "espada", "target": "sacerdote"},
                {"kind": "move", "to": "floresta"},
            ]
        }
    )
    a, b, c = parse_proposal(raw).actions
    assert (type(a), type(b), type(c)) == (CheckAction, AttackAction, MoveAction)
    assert to_command(a, "aria") == "aria: testar furtividade dificil vantagem"
    assert to_command(b, "aria") == "aria: atacar espada sacerdote"
    assert to_command(c, "aria") == "aria: ir floresta"
    assert to_command(RestAction(kind="rest"), "aria") == "aria: descansar"


def test_tolerates_text_around_and_markdown_fences():
    body = '{"actions": [{"kind": "rest"}], "say": "descansem"}'
    for raw in (f"Claro!\n```json\n{body}\n```\nBoa sorte.", f"```\n{body}\n```", body):
        assert parse_proposal(raw).actions[0].kind == "rest"


def test_say_only_and_null_say():
    assert parse_proposal('{"actions": [], "say": "Bram te observa."}').say == "Bram te observa."
    assert parse_proposal('{"say": null}').say == "" and parse_proposal("{}").actions == []


def test_extra_fields_are_ignored():
    p = parse_proposal('{"actions": [{"kind": "rest", "motivo": "cansaço"}], "pensamento": "hm"}')
    assert p.actions[0].kind == "rest"


@pytest.mark.parametrize(
    "raw, fragment",
    [
        ("sem json nenhum", "não contém um objeto JSON"),
        ('{"actions": [', "JSON inválido"),
        ('{"actions": [{"kind": "dance"}]}', "actions.0"),
        ('{"actions": [{"kind": "check", "skill": "x"}]}', "difficulty"),
        ('{"actions": [{"kind": "move"}]}', "actions.0.move.to"),
        ('{"actions": [{"kind": "rest"}, {"kind": "rest"}, {"kind": "rest"}, {"kind": "rest"}]}', "actions"),
        ('{"actions": [{"kind": "move", "to": "Floresta Cinzenta"}]}', "String should match pattern"),
    ],
)
def test_invalid_proposals(raw, fragment):
    with pytest.raises(ProposalError) as info:
        parse_proposal(raw)
    assert fragment in str(info.value)


@pytest.mark.parametrize(
    "bad_id",
    ["floresta; ferir aria 99", "floresta\nferir aria 99", "a b", "Floresta", "../x", ""],
)
def test_ids_cannot_smuggle_extra_commands(bad_id):
    raw = json.dumps({"actions": [{"kind": "move", "to": bad_id}]})
    with pytest.raises(ProposalError):
        parse_proposal(raw)


def test_all_problems_are_reported_together():
    raw = '{"actions": [{"kind": "move", "to": "A B"}, {"kind": "check", "skill": "x"}]}'
    with pytest.raises(ProposalError) as info:
        parse_proposal(raw)
    assert len(info.value.errors) == 2
