"""Gera o contrato JSON Schema em ``contract/`` a partir dos modelos Pydantic.

Uso: ``python -m devaneio.export_schema [--out DIR]``

Os tipos TypeScript do frontend são derivados desses arquivos; nada é escrito duas vezes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaMode

from .schema import Campaign, GameState

# <raiz>/backend/src/devaneio/export_schema.py -> <raiz>/contract
DEFAULT_OUT = Path(__file__).resolve().parents[3] / "contract"

# Campaign é documento de ENTRADA (autorado por pessoas): modo "validation", campos com
# default são opcionais. GameState é SAÍDA do motor: modo "serialization", todo campo está
# sempre presente, e os tipos TypeScript do cliente não ficam cheios de opcionais.
SCHEMAS: dict[str, tuple[type[BaseModel], JsonSchemaMode]] = {
    "campaign.schema.json": (Campaign, "validation"),
    "game_state.schema.json": (GameState, "serialization"),
}


def render(model: type[BaseModel], mode: JsonSchemaMode) -> str:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **model.model_json_schema(mode=mode),
    }
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
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
