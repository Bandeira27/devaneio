"""Erro único do pacote do LLM, levantado quando o servidor falha ou responde fora do formato."""


class LlmError(RuntimeError):
    """Falha ao configurar ou falar com o LLM (rede, HTTP, resposta fora do formato)."""
