import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvState, type StateKind } from './state';

@Component({
  imports: [DvState],
  template: `<dv-state [kind]="kind()"
    >Nada por aqui.<button dvStateAction type="button">Tentar de novo</button></dv-state
  >`,
})
class Host {
  readonly kind = signal<StateKind>('empty');
}

describe('DvState', () => {
  async function render() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const el = (fixture.nativeElement as HTMLElement).querySelector('dv-state') as HTMLElement;
    return { fixture, el, host: fixture.componentInstance };
  }

  it.each([
    ['empty', null],
    ['loading', 'status'],
    ['error', 'alert'],
    ['unavailable', 'status'],
  ] as const)('%s tem o papel certo para o leitor de tela', async (kind, role) => {
    const { fixture, el, host } = await render();
    host.kind.set(kind);
    await fixture.whenStable();
    expect(el.getAttribute('role')).toBe(role);
  });

  it('carregando é aria-busy e mostra os pontos; os outros mostram um ícone', async () => {
    const { fixture, el, host } = await render();
    expect(el.querySelector('dv-icon')).not.toBeNull();
    host.kind.set('loading');
    await fixture.whenStable();
    expect(el.getAttribute('aria-busy')).toBe('true');
    expect(el.querySelector('.pending')).not.toBeNull();
    expect(el.querySelector('dv-icon')).toBeNull();
  });

  it('mostra a mensagem e a ação projetada', async () => {
    const { el } = await render();
    expect(el.querySelector('.message')?.textContent).toContain('Nada por aqui.');
    expect(el.querySelector('[dvStateAction]')?.textContent).toBe('Tentar de novo');
  });
});
