import pytest

from devaneio.engine import add_character, initial_state
from devaneio.llm import LlmError, narrate_with_llm
from devaneio.llm.narration import MAX_CHARS, NARRATOR_SYSTEM, clean_narration

from fakes import ScriptedClient


@pytest.fixture
def state(campaign, rules):
    return add_character(
        initial_state(campaign, rules, 1), rules, character_id="aria", name="Aria"
    ).state


def test_narrates_a_batch_of_events(campaign, state):
    client = ScriptedClient("  Aria avança\n pela trilha,  e a névoa a engole.  ")
    out = narrate_with_llm(
        client, campaign, state, ["Aria testa Furtividade: sucesso", "O grupo vai para a floresta."]
    )
    assert out == "Aria avança pela trilha, e a névoa a engole."
    call = client.calls[0]
    assert call["json_mode"] is False and call["temperature"] == 0.8
    system, user = call["messages"]
    assert system["content"] == NARRATOR_SYSTEM and "Não mude nenhum fato" in system["content"]
    assert "Campanha: A Sombra do Vale" in user["content"]
    assert "Local: Vila de Pedra Alta." in user["content"] and "Grupo: Aria" in user["content"]
    assert "- Aria testa Furtividade: sucesso\n- O grupo vai para a floresta." in user["content"]


@pytest.mark.parametrize(
    "raw, fragment",
    [
        ("", "vazia"),
        ("   \n ", "vazia"),
        ('{"narracao": "x"}', "formato de dados"),
        ("```\ntexto\n```", "formato de dados"),
        ("x" * (MAX_CHARS + 1), "longa demais"),
    ],
)
def test_bad_outputs_are_rejected(campaign, state, raw, fragment):
    with pytest.raises(LlmError, match=fragment):
        narrate_with_llm(ScriptedClient(raw), campaign, state, ["evento"])


def test_client_errors_propagate(campaign, state):
    with pytest.raises(LlmError, match="rede caiu"):
        narrate_with_llm(ScriptedClient(LlmError("rede caiu")), campaign, state, ["evento"])


def test_limit_is_inclusive():
    assert clean_narration("x" * MAX_CHARS) == "x" * MAX_CHARS
