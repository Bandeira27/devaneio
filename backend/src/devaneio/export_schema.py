"""Gera o contrato JSON Schema em ``contract/`` a partir dos modelos Pydantic.

Uso: ``python -m devaneio.export_schema [--out DIR]``

Os tipos TypeScript do frontend são derivados desses arquivos; nada é escrito duas vezes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaMode

from .narration import NarrationPack, NarrationPackExtension
from .rules import RuleSystem, RuleSystemExtension
from .schema import Campaign, GameState
from .server.models import ApiRequests, ApiResponses

# <raiz>/backend/src/devaneio/export_schema.py -> <raiz>/contract
DEFAULT_OUT = Path(__file__).resolve().parents[3] / "contract"

# Entradas (autoradas por pessoas ou pelo cliente) em "validation"; saídas em "serialization".
SCHEMAS: dict[str, tuple[type[BaseModel], JsonSchemaMode]] = {
    "campaign.schema.json": (Campaign, "validation"),
    "rules.schema.json": (RuleSystem, "validation"),
    "rules_extension.schema.json": (RuleSystemExtension, "validation"),
    "narration.schema.json": (NarrationPack, "validation"),
    "narration_extension.schema.json": (NarrationPackExtension, "validation"),
    "game_state.schema.json": (GameState, "serialization"),
    "api_requests.schema.json": (ApiRequests, "validation"),
    "api_responses.schema.json": (ApiResponses, "serialization"),
}


class _NoFieldTitles(GenerateJsonSchema):
    """Remove os títulos de campo do esquema gerado.

    Sem ``title`` por campo, o gerador de tipos TS transformaria cada um em um alias ruidoso
    (``Id1``, ``Turn2``).
    Títulos de modelo (Character, Fact...) continuam.
    """

    def field_title_should_be_set(self, schema: object) -> bool:  # noqa: ARG002 — assinatura herdada de GenerateJsonSchema
        return False


def render(model: type[BaseModel], mode: JsonSchemaMode) -> str:
    """O JSON Schema de um modelo, num modo, pronto para gravar em arquivo."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **model.model_json_schema(mode=mode, schema_generator=_NoFieldTitles),
    }
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Grava todos os esquemas na pasta de saída; devolve o código de saída do processo."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="pasta de saída")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    for name, (model, mode) in SCHEMAS.items():
        path = args.out / name
        path.write_text(render(model, mode), encoding="utf-8")
        print(f"escrito {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
