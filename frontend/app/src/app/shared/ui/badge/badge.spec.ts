import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvBadge, type BadgeTone } from './badge';

@Component({
  imports: [DvBadge],
  template: `<dv-badge [tone]="tone()" [icon]="icon()" [pending]="pending()">já agiu</dv-badge>`,
})
class Host {
  readonly tone = signal<BadgeTone>('neutral');
  readonly icon = signal<'ok' | null>(null);
  readonly pending = signal(false);
}

describe('DvBadge', () => {
  async function render() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const el = (fixture.nativeElement as HTMLElement).querySelector('dv-badge') as HTMLElement;
    return { fixture, el, host: fixture.componentInstance };
  }

  it('o texto está sempre presente e o tom vira classe', async () => {
    const { fixture, el, host } = await render();
    expect(el.textContent?.trim()).toBe('já agiu');
    host.tone.set('danger');
    await fixture.whenStable();
    expect(el.classList.contains('badge--danger')).toBe(true);
  });

  it('com ícone mostra o ícone (escondido do leitor de tela) e o texto continua', async () => {
    const { fixture, el, host } = await render();
    host.icon.set('ok');
    await fixture.whenStable();
    expect(el.querySelector('dv-icon')?.getAttribute('aria-hidden')).toBe('true');
    expect(el.textContent).toContain('já agiu');
  });

  it('pendente troca o ícone pelo ponto que pulsa', async () => {
    const { fixture, el, host } = await render();
    host.icon.set('ok');
    host.pending.set(true);
    await fixture.whenStable();
    expect(el.querySelector('.badge__dot')).not.toBeNull();
    expect(el.querySelector('dv-icon')).toBeNull();
  });
});
