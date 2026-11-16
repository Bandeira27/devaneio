/** O erro com que uma espera abortada termina: o laço o reconhece e sai sem tratá-lo como falha. */
export function abortError(): DOMException {
  return new DOMException('abortado', 'AbortError');
}

/**
 * Uma promessa que também termina (rejeitada com `AbortError`) quando `signal` é abortado, sem deixar ouvinte
 * pendurado: o ouvinte de abort sai assim que a promessa se resolve de qualquer jeito.
 *
 * @param signal O sinal que cancela a espera. Se já veio abortado, rejeita na hora e `start` nem roda.
 * @param start Começa a espera (timer, requisição, ouvinte) e devolve a função que a desfaz.
 */
export function abortable<T>(
  signal: AbortSignal,
  start: (resolve: (value: T) => void, reject: (reason: unknown) => void) => () => void,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    if (signal.aborted) {
      reject(abortError());
      return;
    }
    let cleanup = (): void => undefined;
    const onAbort = (): void => {
      cleanup();
      reject(abortError());
    };
    const settle =
      <A>(finish: (value: A) => void) =>
      (value: A): void => {
        signal.removeEventListener('abort', onAbort);
        finish(value);
      };
    signal.addEventListener('abort', onAbort, { once: true });
    cleanup = start(settle(resolve), settle(reject));
  });
}
