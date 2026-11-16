import { ApiFailure } from './api-failure';

/**
 * Envia com a revisão atual da mesa e, se o servidor responder `stale_revision` (a mesa andou enquanto o jogador
 * decidia), relê a mesa com `refresh` e envia de novo, uma única vez. Qualquer outra falha segue adiante.
 *
 * @param send Faz o envio com a revisão dada.
 * @param revision Devolve a revisão que a tela conhece agora.
 * @param refresh Relê a mesa e deixa `revision()` atualizada.
 */
export async function withStaleRetry<T>(
  send: (revision: number) => Promise<T>,
  revision: () => number,
  refresh: () => Promise<void>,
): Promise<T> {
  try {
    return await send(revision());
  } catch (error) {
    if (!(error instanceof ApiFailure) || error.code !== 'stale_revision') {
      throw error;
    }
    await refresh();
    return send(revision());
  }
}
