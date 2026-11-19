import { RevealClock, RevealQueue } from './table.reveal';

function fakeClock(step = 1000) {
  let time = 0;
  const timers: { at: number; fn: () => void; live: boolean }[] = [];
  const clock: RevealClock = {
    stepMs: () => step,
    now: () => time,
    setTimer: (fn, ms) => {
      const timer = { at: time + ms, fn, live: true };
      timers.push(timer);
      return () => {
        timer.live = false;
      };
    },
  };
  const advance = (ms: number) => {
    const end = time + ms;
    for (;;) {
      const next = timers.filter((t) => t.live && t.at <= end).sort((a, b) => a.at - b.at)[0];
      if (!next) {
        break;
      }
      time = next.at;
      next.live = false;
      next.fn();
    }
    time = end;
  };
  return { clock, advance };
}

describe('RevealQueue', () => {
  it('o primeiro texto espera um passo, nunca aparece na hora', () => {
    const { clock, advance } = fakeClock();
    const queue = new RevealQueue(clock);
    const shown: string[] = [];
    queue.enqueue(10, () => shown.push('a'));
    expect(shown).toEqual([]);
    advance(999);
    expect(shown).toEqual([]);
    advance(1);
    expect(shown).toEqual(['a']);
  });

  it('cada texto espera o anterior ser lido, pelo tamanho dele', () => {
    const { clock, advance } = fakeClock();
    const queue = new RevealQueue(clock);
    const shown: string[] = [];
    queue.enqueue(200, () => shown.push('longo')); // 3 passos
    queue.enqueue(10, () => shown.push('curto'));
    advance(1000);
    expect(shown).toEqual(['longo']);
    advance(2999);
    expect(shown).toEqual(['longo']);
    advance(1);
    expect(shown).toEqual(['longo', 'curto']);
  });

  it('um lote grande segue em fila, um de cada vez', () => {
    const { clock, advance } = fakeClock();
    const queue = new RevealQueue(clock);
    const shown: number[] = [];
    for (let i = 0; i < 10; i++) {
      queue.enqueue(10, () => shown.push(i));
    }
    advance(1000);
    expect(shown).toEqual([0]);
    advance(9000);
    expect(shown).toHaveLength(10);
  });

  it('um lote que chega com a fila andando espera ela acabar', () => {
    const { clock, advance } = fakeClock();
    const queue = new RevealQueue(clock);
    const shown: string[] = [];
    queue.enqueue(10, () => shown.push('a'));
    queue.enqueue(10, () => shown.push('b'));
    advance(500);
    queue.enqueue(10, () => shown.push('c'));
    advance(1500); // 2000: a e b
    expect(shown).toEqual(['a', 'b']);
    advance(1000);
    expect(shown).toEqual(['a', 'b', 'c']);
  });

  it('com a fila parada, o texto seguinte volta a esperar o passo inicial', () => {
    const { clock, advance } = fakeClock();
    const queue = new RevealQueue(clock);
    const shown: string[] = [];
    queue.enqueue(10, () => shown.push('a'));
    advance(10_000);
    queue.enqueue(10, () => shown.push('b'));
    advance(999);
    expect(shown).toEqual(['a']);
    advance(1);
    expect(shown).toEqual(['a', 'b']);
  });

  it('idle só volta quando tudo apareceu', () => {
    const { clock, advance } = fakeClock();
    const queue = new RevealQueue(clock);
    expect(queue.idle()).toBe(true);
    queue.enqueue(10, () => undefined);
    queue.enqueue(10, () => undefined);
    expect(queue.idle()).toBe(false);
    advance(1000);
    expect(queue.idle()).toBe(false);
    advance(1000);
    expect(queue.idle()).toBe(true);
  });

  it('dispose cancela o que falta', () => {
    const { clock, advance } = fakeClock();
    const queue = new RevealQueue(clock);
    const shown: string[] = [];
    queue.enqueue(10, () => shown.push('a'));
    queue.dispose();
    advance(5000);
    expect(shown).toEqual([]);
    expect(queue.idle()).toBe(true);
  });
});
