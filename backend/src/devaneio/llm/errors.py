class LlmError(RuntimeError):
    """Falha ao configurar ou falar com o LLM (rede, HTTP, resposta fora do formato)."""
