/** Parâmetros do long-poll de eventos: de onde ler, a partir de qual fala e de qual mensagem do chat e quanto esperar (segundos). */
export interface EventsQuery {
  since: number;
  sinceTalk: number;
  sinceChat: number;
  wait: number;
}
