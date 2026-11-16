"""A política de supressões do front (TS, HTML e JS) em scripts/check_suppressions.py."""

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("tomllib", reason="o script exige Python >= 3.11")

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_suppressions.py"


@pytest.fixture
def script(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("check_suppressions_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    return module


def problems(script, line):
    return script.check_front_line("a.ts:1", line)


@pytest.mark.parametrize(
    "line",
    [
        "// @ts-ignore",
        "// @ts-ignore -- motivo",
        "/* @ts-nocheck */",
        "  // @ts-ignore: o tipo está errado",
    ],
)
def test_ts_ignore_and_nocheck_are_forbidden(script, line):
    (message,) = problems(script, line)
    assert "são proibidos" in message


def test_ts_expect_error_needs_a_justification(script):
    assert problems(script, "// @ts-expect-error -- o contrato gerado ainda não tem o campo") == []
    assert problems(script, "// @ts-expect-error — o contrato gerado ainda não tem o campo") == []
    (message,) = problems(script, "// @ts-expect-error")
    assert "sem justificativa" in message
    (message,) = problems(script, "// @ts-expect-error o tipo está errado")
    assert "sem justificativa" in message


@pytest.mark.parametrize(
    "line",
    [
        "// eslint-disable-next-line no-console -- log de diagnóstico do servidor de dev",
        "// eslint-disable-line @typescript-eslint/no-explicit-any -- o contrato gerado usa any",
        "/* eslint-disable no-restricted-imports, no-console -- gerado */",
        "<!-- eslint-disable @angular-eslint/template/alt-text -- imagem decorativa -->",
    ],
)
def test_a_named_and_justified_eslint_disable_is_fine(script, line):
    assert problems(script, line) == []


@pytest.mark.parametrize(
    ("line", "fragment"),
    [
        ("// eslint-disable", "sem a regra"),
        ("/* eslint-disable */", "sem a regra"),
        ("// eslint-disable-next-line", "sem a regra"),
        ("// eslint-disable-next-line no-console", "sem justificativa"),
        ("// eslint-disable-line no-console -- ", "sem justificativa"),
        ("<!-- eslint-disable -->", "sem a regra"),
    ],
)
def test_a_bare_or_unjustified_eslint_disable_is_refused(script, line, fragment):
    found = problems(script, line)
    assert found
    assert any(fragment in message for message in found)


def test_lines_without_suppressions_are_clean(script):
    for line in ("const a = 1;", "// comentário comum", "<p>{{ texto }}</p>", "eslint is great"):
        assert problems(script, line) == []


def test_files_are_scanned_with_their_line_numbers(script, tmp_path):
    bad = tmp_path / "frontend" / "app" / "src" / "x.ts"
    bad.parent.mkdir(parents=True)
    bad.write_text("const a = 1;\n// @ts-ignore\nconst b = 2;\n", encoding="utf-8")
    good = tmp_path / "frontend" / "app" / "src" / "y.ts"
    good.write_text("// eslint-disable-next-line no-console -- diagnóstico\nconsole.log(1);\n")
    script.errors.clear()
    script.check_front_inline([bad, good])
    assert len(script.errors) == 1
    assert script.errors[0].startswith("frontend/app/src/x.ts:2:")


def test_the_generated_contract_is_left_out(script):
    assert any(prefix == "frontend/src/contract/" for prefix in script.FRONT_SKIP)
    # O cabeçalho gerado traz `eslint-disable` sem regra: sem a exclusão, o gate reprovaria o contrato.
    assert problems(script, "/* eslint-disable */")


def test_the_real_repository_passes(script):
    """Os arquivos rastreados do front (fora o contrato gerado) respeitam a política."""
    real = importlib.util.spec_from_file_location("real", SCRIPT)
    assert real is not None
    assert real.loader is not None
    module = importlib.util.module_from_spec(real)
    real.loader.exec_module(module)
    module.errors.clear()
    module.check_front_inline()
    assert module.errors == []
