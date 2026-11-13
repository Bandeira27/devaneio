"""Tipos e base compartilhados por todos os modelos do esquema."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# Identificadores são slugs: minúsculas, dígitos, '_' e '-', começando por letra ou dígito.
# Eles aparecem em templates, em chamadas estruturadas do LLM e em URLs; um formato
# restrito evita ambiguidade (espaços, maiúsculas, acentos) desde o início.
Id = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]*$")]


class StrictModel(BaseModel):
    """Base de todos os modelos: campo desconhecido é erro, nunca dado ignorado."""

    model_config = ConfigDict(
        extra="forbid",
        # Só afeta o JSON Schema em modo "serialization" (usado para GameState): o que o
        # motor emite sempre traz todos os campos, então o cliente não os vê como opcionais.
        json_schema_serialization_defaults_required=True,
    )
