import { abortError, abortable } from './abortable';

describe('abortable', () => {
  it('resolve com o valor e desfaz nada quando não é abortado', async () => {
    const controller = new AbortController();
    const cleanup = vi.fn();
    const value = await abortable<number>(controller.signal, (resolve) => {
      resolve(7);
      return cleanup;
    });
    expect(value).toBe(7);
    controller.abort(); // depois de resolvida, abortar não faz mais nada
    expect(cleanup).not.toHaveBeenCalled();
  });

  it('rejeita com AbortError e desfaz a espera ao abortar', async () => {
    const controller = new AbortController();
    const cleanup = vi.fn();
    const pending = abortable<undefined>(controller.signal, () => cleanup);
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
    expect(cleanup).toHaveBeenCalledOnce();
  });

  it('com o sinal já abortado rejeita na hora e nem começa', async () => {
    const controller = new AbortController();
    controller.abort();
    const start = vi.fn(() => () => undefined);
    await expect(abortable<undefined>(controller.signal, start)).rejects.toBeInstanceOf(
      DOMException,
    );
    expect(start).not.toHaveBeenCalled();
  });

  it('propaga a falha da própria espera', async () => {
    const controller = new AbortController();
    const boom = new Error('boom');
    await expect(
      abortable<undefined>(controller.signal, (_resolve, reject) => {
        reject(boom);
        return () => undefined;
      }),
    ).rejects.toBe(boom);
  });

  it('abortError é um AbortError', () => {
    expect(abortError().name).toBe('AbortError');
  });
});
