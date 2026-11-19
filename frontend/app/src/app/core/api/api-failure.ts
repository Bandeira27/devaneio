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

/**
 * Mensagem humana por código de erro do servidor: o que aconteceu e, quando há, o que fazer. Os códigos são estáveis;
 * a mensagem do servidor é técnica (minúscula, sem ponto, com ids) e só serve de reserva.
 */
const FRIENDLY: Readonly<Record<string, string>> = {
  network: 'Sem conexão com o servidor. Confira a rede e tente de novo.',
  invalid_invite: 'Esse convite não vale. Peça um link novo ao anfitrião.',
  unauthorized: 'Sua sessão nesta mesa expirou. Volte ao início e entre de novo pelo convite.',
  table_not_found: 'Essa mesa não existe mais no servidor.',
  already_acted: 'Você já agiu neste turno. Espere o grupo.',
  character_limit: 'Você já tem o máximo de personagens nesta mesa.',
  game_over: 'A partida terminou: não dá mais para agir.',
  not_started: 'A partida ainda não começou. Espere o anfitrião iniciar.',
  paused: 'A partida está pausada pelo anfitrião.',
  ended: 'A partida foi encerrada pelo anfitrião.',
  table_ended: 'Essa partida já foi encerrada: não dá mais para entrar.',
  no_characters: 'Crie ao menos um personagem antes de iniciar.',
  invalid_transition: 'Isso não dá para fazer na fase em que a partida está.',
  table_full: 'A mesa está cheia.',
  table_limit: 'O servidor já tem o máximo de mesas. Tente mais tarde.',
  stale_revision: 'A mesa mudou enquanto você agia. Tente de novo.',
  no_character: 'Você ainda não tem personagem nesta mesa. Crie um para agir.',
  say_rate_limited: 'Calma: espere um instante antes de falar de novo.',
  say_busy: 'O mestre ainda está respondendo. Espere um instante.',
  copilot_busy: 'O copiloto ainda está respondendo. Espere um instante.',
  copilot_rate_limited: 'O copiloto precisa de um instante antes da próxima pergunta.',
  llm_unavailable: 'O mestre de IA não respondeu. Tente de novo.',
  context_too_large: 'A campanha é grande demais para o copiloto responder.',
  campaign_not_found: 'Essa campanha não está mais no servidor. Escolha outra.',
  llm_disabled: 'Esta mesa não tem mestre de IA ligado.',
  forbidden: 'Isso é só do anfitrião da mesa.',
  name_taken: 'Já existe alguém com esse nome na mesa. Escolha outro.',
  payload_too_large: 'O texto é grande demais.',
  request_timeout: 'A conexão demorou demais. Tente de novo.',
  busy: 'O servidor está ocupado. Tente de novo em instantes.',
  internal: 'O servidor falhou. Tente de novo em instantes.',
};

/**
 * Vale tentar de novo depois? Falha da API diz por `retryable` (rede, tempo, servidor); mesa que sumiu (404) e sessão
 * vencida (401) não melhoram tentando. O que não é falha da API (um erro de programação) deixa tentar, por falta de
 * melhor saída.
 */
export function isRetryable(error: unknown): boolean {
  return !(error instanceof ApiFailure) || error.retryable;
}

/** "regra quebrada" → "Regra quebrada." (a frase do servidor, apresentável). */
function sentence(text: string): string {
  const trimmed = text.trim();
  if (trimmed === '') {
    return 'Algo deu errado. Tente de novo.';
  }
  const capital = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
  return /[.!?…]$/.test(capital) ? capital : `${capital}.`;
}

/**
 * Texto de erro para a tela. Código conhecido vira a mensagem humana; `command_refused` mantém a explicação do servidor
 * (é ela que diz por que a regra recusou); o resto usa a frase do servidor, só ajeitada. O que não é falha da API
 * ganha uma frase genérica.
 */
export function messageOf(error: unknown): string {
  if (!(error instanceof ApiFailure)) {
    return 'Algo deu errado. Tente de novo.';
  }
  if (error.code === 'command_refused') {
    return sentence(error.message);
  }
  return FRIENDLY[error.code] ?? sentence(error.message);
}
