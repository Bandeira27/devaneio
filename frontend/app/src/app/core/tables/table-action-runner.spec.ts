import { ApiFailure } from '../api/api-failure';
import { TableActionRunner } from './table-action-runner';

describe('TableActionRunner', () => {
  it('marca a mesa como ocupada enquanto a ação roda e a solta no fim', async () => {
    const runner = new TableActionRunner();
    let during: string | null = null;
    const done = await runner.run('mesa', async () => {
      during = runner.busy();
    });
    expect([done, during, runner.busy(), runner.error()]).toEqual([true, 'mesa', null, '']);
  });

  it('uma falha vira a mensagem da tela, devolve false e também solta a mesa', async () => {
    const runner = new TableActionRunner();
    const done = await runner.run('mesa', async () => {
      throw new ApiFailure(0, 'network', 'sem rede');
    });
    expect(done).toBe(false);
    expect(runner.error()).not.toBe('');
    expect(runner.busy()).toBeNull();
  });

  it('uma ação nova limpa o erro da anterior', async () => {
    const runner = new TableActionRunner();
    await runner.run('mesa', () => Promise.reject(new Error('x')));
    await runner.run('mesa', () => Promise.resolve());
    expect(runner.error()).toBe('');
  });
});
