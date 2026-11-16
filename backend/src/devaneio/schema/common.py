"""Tipos e base compartilhados por todos os modelos do esquema."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# Identificadores são slugs (minúsculas, dígitos, '_' e '-'): aparecem em templates, no LLM e em URLs.
Id = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]*$")]


class StrictModel(BaseModel):
    """Base de todos os modelos: campo desconhecido é erro, nunca dado ignorado."""

    model_config = ConfigDict(
        extra="forbid",
        # Em "serialization" (GameState) o cliente não vê os campos com default como opcionais.
        json_schema_serialization_defaults_required=True,
    )
