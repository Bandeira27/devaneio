import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvPips } from './pips';

@Component({ imports: [DvPips], template: `<dv-pips [value]="value()" [max]="max()" />` })
class Host {
  readonly value = signal(8);
  readonly max = signal(10);
}

describe('DvPips', () => {
  async function render() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const el = (fixture.nativeElement as HTMLElement).querySelector('dv-pips') as HTMLElement;
    return { el, host: fixture.componentInstance, settle: () => fixture.whenStable() };
  }
  const count = (el: HTMLElement, kind: string) => el.querySelectorAll(`.pip--${kind}`).length;

  it('um ponto cheio por hp atual e um vazio por hp perdido', async () => {
    const { el } = await render();
    expect([count(el, 'full'), count(el, 'empty')]).toEqual([8, 2]);
  });

  it('mostra o número exato ao lado dos pontos, escondido do leitor de tela (que já ouve o texto alternativo)', async () => {
    const { el } = await render();
    const number = el.querySelector('.pips__count') as HTMLElement;
    expect(number.textContent?.trim()).toBe('8/10');
    expect(number.getAttribute('aria-hidden')).toBe('true');
  });

  it('tem texto alternativo com os números, e os pontos ficam escondidos do leitor de tela', async () => {
    const { el } = await render();
    expect(el.getAttribute('role')).toBe('img');
    expect(el.getAttribute('aria-label')).toBe('pontos de vida: 8 de 10');
    expect(el.querySelector('.pip')?.getAttribute('aria-hidden')).toBe('true');
  });

  it('hp zero é tudo vazio, hp acima do máximo não passa do máximo e hp negativo vira zero', async () => {
    const { el, host, settle } = await render();
    host.value.set(0);
    await settle();
    expect([count(el, 'full'), count(el, 'empty')]).toEqual([0, 10]);
    host.value.set(-3);
    await settle();
    expect(count(el, 'full')).toBe(0);
    host.value.set(14);
    await settle();
    expect(count(el, 'empty')).toBe(0);
  });

  it('limita a quantidade de pontos desenhados', async () => {
    const { el, host, settle } = await render();
    host.max.set(500);
    host.value.set(400);
    await settle();
    expect(count(el, 'full') + count(el, 'empty')).toBeLessThanOrEqual(24);
  });
});
