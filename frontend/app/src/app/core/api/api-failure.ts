import { HttpErrorResponse } from '@angular/common/http';

/**
 * Falha da API como o cliente a enxerga: `code` é o código estável do servidor (`stale_revision`,
 * `copilot_busy`...) e `message` já vem em português. Falha de rede (status 0) vira o código `network`.
 */
export class ApiFailure extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiFailure';
  }

  /** Vale tentar de novo depois: rede fora, tempo esgotado, limite de ritmo ou erro do servidor. */
  get retryable(): boolean {
    return this.status === 0 || this.status === 408 || this.status === 429 || this.status >= 500;
  }

  static from(response: HttpErrorResponse): ApiFailure {
    if (response.status === 0) {
      return new ApiFailure(0, 'network', 'Sem conexão com o servidor.');
    }
    const body: unknown = response.error;
    if (typeof body === 'object' && body !== null && 'error' in body) {
      const error: unknown = body.error;
      if (typeof error === 'object' && error !== null && 'code' in error && 'message' in error) {
        const { code, message } = error;
        if (typeof code === 'string' && typeof message === 'string') {
          return new ApiFailure(response.status, code, message);
        }
      }
    }
    return new ApiFailure(response.status, 'unknown', 'O servidor respondeu algo inesperado.');
  }
}

/** Texto de erro para a tela: o do servidor (já em português) ou um genérico para o que não é falha da API. */
export function messageOf(error: unknown): string {
  return error instanceof ApiFailure ? error.message : 'Algo deu errado. Tente de novo.';
}
