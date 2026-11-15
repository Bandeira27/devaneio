import pytest

from devaneio.narration import Grammar, GrammarError, referenced_symbols
from devaneio.narration.grammar import MAX_EXPANSIONS
from devaneio.rng import Rng

RULES = {
    "frase": ["#ator# #verbo# #alvo#.", "Sem hesitar, #ator# #verbo# #alvo#!"],
    "verbo": ["ataca", "encara", "observa"],
    "cumprimento": ["Olá, #nome#."],
}


def test_referenced_symbols():
    assert referenced_symbols("#a# e #b.c# e #a#") == ["a", "b.c", "a"]
    assert referenced_symbols("sem referências") == []


def test_expansion_is_deterministic_for_a_given_rng():
    g = Grammar(RULES)
    v = {"ator": "Aria", "alvo": "o culto"}
    a = g.expand("frase", v, Rng(3))
    b = g.expand("frase", v, Rng(3))
    assert a == b
    assert a.startswith(("Aria ", "Sem hesitar, Aria "))
    assert "o culto" in a


def test_different_rngs_eventually_pick_different_options():
    g = Grammar(RULES)
    v = {"ator": "Aria", "alvo": "o culto"}
    assert len({g.expand("frase", v, Rng(seed)) for seed in range(20)}) > 1


def test_variables_win_over_rules_and_are_substituted_verbatim():
    g = Grammar({"x": ["regra"], "f": ["#x#"]})
    assert g.expand("f", {"x": "variável"}, Rng(0)) == "variável"
    assert g.expand("f", {}, Rng(0)) == "regra"


def test_nested_expansion():
    g = Grammar({"a": ["<#b#>"], "b": ["[#c#]"], "c": ["fim"]})
    assert g.expand("a", {}, Rng(0)) == "<[fim]>"


def test_missing_symbol_is_an_error():
    g = Grammar(RULES)
    with pytest.raises(GrammarError, match="símbolo 'nome' não é regra nem variável"):
        g.expand("cumprimento", {}, Rng(0))
    with pytest.raises(GrammarError, match="'inexistente'"):
        g.expand("inexistente", {}, Rng(0))


def test_runaway_recursion_is_an_error():
    g = Grammar({"loop": ["#loop#"]})
    with pytest.raises(GrammarError, match="recursão profunda"):
        g.expand("loop", {}, Rng(0))


def test_empty_rule_is_rejected():
    with pytest.raises(GrammarError, match="regra 'vazia' não tem alternativas"):
        Grammar({"vazia": []})


def test_undefined_reports_unknown_references_with_transitive_variables():
    g = Grammar(RULES)
    assert g.undefined() == [
        "cumprimento: #nome#",
        "frase: #alvo#",
        "frase: #ator#",
    ]
    assert g.undefined({"frase": ["ator", "alvo"], "cumprimento": ["nome"]}) == []
    # auxiliar pode usar a variável se toda raiz que o alcança a permite
    g2 = Grammar({"raiz": ["#aux#"], "outra": ["#aux#"], "aux": ["#var#"], "solta": ["#x#"]})
    assert g2.undefined({"raiz": ["var"], "outra": ["var"]}) == ["solta: #x#"]
    assert g2.undefined({"raiz": ["var"], "outra": []}) == ["outra: #var#", "solta: #x#"]


def test_the_expansion_budget_stops_a_blow_up_at_runtime():
    rules = {f"b{i}": [f"#b{i + 1}##b{i + 1}#"] for i in range(15)}
    rules["b15"] = ["x"]
    with pytest.raises(GrammarError, match=f"mais de {MAX_EXPANSIONS} passos"):
        Grammar(rules).expand("b0", {}, Rng(1))


def test_cycles_and_worst_length():
    grammar = Grammar({"a": ["#b# #v#"], "b": ["oi"]})
    assert grammar.cycles() == []
    assert grammar.worst_length("a", {"v"}) == 2 + 1 + 100  # "oi" + " " + variável
    assert Grammar({"a": ["#b#"], "b": ["#a#"]}).cycles() == ["a -> b -> a"]
    assert Grammar({"a": ["#a#"]}).cycles() == ["a -> a"]
