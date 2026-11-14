import pytest

from devaneio.rng import Rng
from devaneio.rules.expression import (
    Attr,
    BinOp,
    Dice,
    ExpressionError,
    Neg,
    Num,
    evaluate,
    identifiers,
    parse,
    roll,
)

ATTRS = {"FOR": 2, "AGI": 1}


@pytest.mark.parametrize(
    ("text", "total"),
    [
        ("3", 3),
        ("3 + 4", 7),
        ("10 - 4 - 3", 3),  # associativo à esquerda
        ("2 + 3 * 4", 14),  # precedência
        ("(2 + 3) * 4", 20),
        ("-3 + 5", 2),
        ("-(2 + 1) * 2", -6),
        ("FOR", 2),
        ("FOR * 2 + AGI", 5),
        ("  FOR+1 ", 3),
    ],
)
def test_arithmetic_without_dice(text, total):
    result = roll(text, ATTRS, Rng(0))
    assert result.total == total
    assert result.rolls == ()


def test_parse_builds_expected_ast():
    assert parse("2d6 + FOR") == BinOp("+", Dice(2, 6), Attr("FOR"))
    assert parse("d20") == Dice(1, 20)
    assert parse("-FOR") == Neg(Attr("FOR"))
    assert parse("1 + 2 * 3") == BinOp("+", Num(1), BinOp("*", Num(2), Num(3)))


def test_dice_consume_rng_in_order_and_report_values():
    rng = Rng(42)
    expected = [Rng(42).roll(6), Rng(42, draws=1).roll(6), Rng(42, draws=2).roll(4)]
    result = roll("2d6 + 1d4 + FOR", ATTRS, rng)
    assert [v for r in result.rolls for v in r.values] == expected
    assert result.total == sum(expected) + 2
    assert result.rolls[0].dice == "2d6"
    assert result.rolls[1].dice == "1d4"
    assert rng.draws == 3


def test_same_rng_state_gives_same_roll():
    assert roll("3d6 + FOR", ATTRS, Rng(9)) == roll("3d6 + FOR", ATTRS, Rng(9))


def test_identifiers():
    assert identifiers(parse("2d6 + FOR - (AGI * 2)")) == {"FOR", "AGI"}
    assert identifiers(parse("2d6 + 1")) == set()


def test_missing_attribute_is_an_error():
    with pytest.raises(ExpressionError, match="atributo 'MEN' não existe"):
        evaluate(parse("2d6 + MEN"), ATTRS, Rng(0))


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "2 +",
        "+ 2",
        "(2 + 3",
        "2 + 3)",
        "2 3",
        "2 / 3",
        "for",  # identificadores são maiúsculos
        "2d",
        "d1",  # mínimo 2 lados
        "0d6",
        "101d6",
        "1d1001",
        "2.5",
        "FOR AGI",
    ],
)
def test_syntax_errors(text):
    with pytest.raises(ExpressionError):
        parse(text)
