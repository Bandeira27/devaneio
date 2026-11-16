/** Parâmetros do long-poll de eventos: de onde ler, a partir de qual fala e quanto esperar (segundos). */
export interface EventsQuery {
  since: number;
  sinceTalk: number;
  wait: number;
}
