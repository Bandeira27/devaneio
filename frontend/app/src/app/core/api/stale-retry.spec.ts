import { ApiFailure } from './api-failure';
import { withStaleRetry } from './stale-retry';

const stale = () => new ApiFailure(409, 'stale_revision', 'A mesa mudou.');

describe('withStaleRetry', () => {
  it('envia uma vez com a revisão atual quando dá certo', async () => {
    const send = vi.fn().mockResolvedValue('ok');
    const refresh = vi.fn().mockResolvedValue(undefined);
    expect(await withStaleRetry(send, () => 3, refresh)).toBe('ok');
    expect(send).toHaveBeenCalledExactlyOnceWith(3);
    expect(refresh).not.toHaveBeenCalled();
  });

  it('em stale_revision relê e repete uma vez com a revisão nova', async () => {
    let revision = 3;
    const send = vi.fn().mockRejectedValueOnce(stale()).mockResolvedValueOnce('ok');
    const refresh = vi.fn(async () => {
      revision = 8;
    });
    expect(await withStaleRetry(send, () => revision, refresh)).toBe('ok');
    expect(send.mock.calls).toEqual([[3], [8]]);
    expect(refresh).toHaveBeenCalledOnce();
  });

  it('desiste depois de uma repetição', async () => {
    const send = vi.fn().mockRejectedValue(stale());
    await expect(
      withStaleRetry(
        send,
        () => 1,
        async () => undefined,
      ),
    ).rejects.toBeInstanceOf(ApiFailure);
    expect(send).toHaveBeenCalledTimes(2);
  });

  it('não repete outras falhas', async () => {
    const send = vi.fn().mockRejectedValue(new ApiFailure(422, 'bad_command', 'x'));
    const refresh = vi.fn();
    await expect(withStaleRetry(send, () => 1, refresh)).rejects.toMatchObject({
      code: 'bad_command',
    });
    expect(send).toHaveBeenCalledOnce();
    expect(refresh).not.toHaveBeenCalled();
  });
});
