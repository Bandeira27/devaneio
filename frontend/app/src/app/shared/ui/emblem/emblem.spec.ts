import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { campaignEmblem } from '@shared/game/emblem';
import { DvEmblem } from './emblem';

@Component({
  imports: [DvEmblem],
  template: `<dv-emblem [campaignId]="id()" [size]="size()" />`,
})
class Host {
  readonly id = signal('sombra-do-vale');
  readonly size = signal<'md' | 'lg'>('md');
}

describe('DvEmblem', () => {
  async function render() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const el = (fixture.nativeElement as HTMLElement).querySelector('dv-emblem') as HTMLElement;
    return { fixture, el, host: fixture.componentInstance };
  }

  it('é decorativo e usa o ícone e o tom que o id escolhe', async () => {
    const { el } = await render();
    const emblem = campaignEmblem('sombra-do-vale');
    expect(el.getAttribute('aria-hidden')).toBe('true');
    expect(el.classList.contains(`emblem--${emblem.tone}`)).toBe(true);
    expect(el.querySelector('dv-icon svg path')).not.toBeNull(); // o ícone que o id escolheu
  });

  it('o tamanho vira classe', async () => {
    const { fixture, el, host } = await render();
    host.size.set('lg');
    await fixture.whenStable();
    expect(el.classList.contains('emblem--lg')).toBe(true);
  });
});
