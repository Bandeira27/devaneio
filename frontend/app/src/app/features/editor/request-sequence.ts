/**
 * Faz só a resposta do pedido mais recente valer. Quem pede chama `begin()` antes de ir à rede e, ao receber a resposta
 * (ou o erro), só a aplica se o bilhete ainda for o atual; um pedido mais novo, ou `invalidate()`, deixa os anteriores
 * para trás. Serve para o que o autor muda enquanto o servidor ainda responde (a conferência e a prévia).
 */
export class RequestSequence {
  private current = 0;

  /** Começa um pedido e devolve o bilhete dele: `true` enquanto nenhum pedido mais novo ou `invalidate()` o superou. */
  begin(): () => boolean {
    const mine = ++this.current;
    return () => mine === this.current;
  }

  /** O que está em andamento deixa de valer, sem começar outro pedido. */
  invalidate(): void {
    this.current++;
  }
}
