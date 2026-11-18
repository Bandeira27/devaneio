import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvPlayClock } from './play-clock';

@Component({
  imports: [DvPlayClock],
  template: `<dv-play-clock [phase]="phase()" [seconds]="seconds()" [receivedAt]="receivedAt()" />`,
})
class Host {
  readonly phase = signal<'lobby' | 'running' | 'paused' | 'ended'>('running');
  readonly seconds = signal(3723);
  readonly receivedAt = signal(Date.now());
}

describe('DvPlayClock', () => {
  afterEach(() => vi.useRealTimers());

  async function render() {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] });
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const el = (fixture.nativeElement as HTMLElement).querySelector('dv-play-clock') as HTMLElement;
    return { fixture, el, host: fixture.componentInstance };
  }
  const visual = (el: HTMLElement) => el.querySelector('.clock__time')?.textContent;

  it('mostra o rótulo da fase e o relógio, e diz o tempo em palavras para o leitor de tela', async () => {
    const { el } = await render();
    expect(el.querySelector('.clock__label')?.textContent).toBe('Rodando');
    expect(visual(el)).toBe('1:02:03');
    expect(el.querySelector('.clock__time')?.getAttribute('aria-hidden')).toBe('true');
    expect(el.querySelector('.dv-visually-hidden')?.textContent).toBe(
      'Rodando: 1 hora e 2 minutos',
    );
  });

  it('enquanto roda, anda sozinho a cada segundo', async () => {
    const { fixture, el } = await render();
    vi.advanceTimersByTime(3000);
    await fixture.whenStable();
    expect(visual(el)).toBe('1:02:06');
  });

  it('na pausa e no fim fica parado', async () => {
    const { fixture, el, host } = await render();
    host.phase.set('paused');
    await fixture.whenStable();
    expect(el.querySelector('.clock__label')?.textContent).toBe('Pausada');
    vi.advanceTimersByTime(5000);
    await fixture.whenStable();
    expect(visual(el)).toBe('1:02:03');
    host.phase.set('ended');
    await fixture.whenStable();
    expect(el.querySelector('.clock__label')?.textContent).toBe('Encerrada');
  });

  it('na sala de espera não mostra nada', async () => {
    const { fixture, el, host } = await render();
    host.phase.set('lobby');
    await fixture.whenStable();
    expect(el.textContent?.trim()).toBe('');
  });
});
