"""Tipos e base compartilhados por todos os modelos do esquema."""

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# Identificadores são slugs (minúsculas, dígitos, '_' e '-'): aparecem em templates, no LLM e em URLs.
ID_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"
ID_REGEX = re.compile(ID_PATTERN)  # use com ``fullmatch``: ``$`` aceitaria um ``\n`` no fim
Id = Annotated[str, StringConstraints(pattern=ID_PATTERN)]


class StrictModel(BaseModel):
    """Base de todos os modelos: campo desconhecido é erro, nunca dado ignorado."""

    model_config = ConfigDict(
        extra="forbid",
        # Em "serialization" (GameState) o cliente não vê os campos com default como opcionais.
        json_schema_serialization_defaults_required=True,
    )
