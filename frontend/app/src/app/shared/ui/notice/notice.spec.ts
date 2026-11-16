import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import type { NoticeKind } from './notice';
import { DvNotice } from './notice';

@Component({
  imports: [DvNotice],
  template: `<dv-notice [kind]="kind()">Algo aconteceu.</dv-notice>`,
})
class Host {
  readonly kind = signal<NoticeKind>('info');
}

describe('DvNotice', () => {
  async function render(): Promise<{ el: HTMLElement; host: Host; settle: () => Promise<void> }> {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    return {
      el: (fixture.nativeElement as HTMLElement).querySelector('dv-notice') as HTMLElement,
      host: fixture.componentInstance,
      settle: () => fixture.whenStable(),
    };
  }

  it('aviso de informação é status e o leitor de tela ouve o prefixo', async () => {
    const { el } = await render();
    expect(el.getAttribute('role')).toBe('status');
    expect(el.textContent).toContain('Aviso: Algo aconteceu.');
    expect(el.classList.contains('notice--info')).toBe(true);
  });

  it('erro é alerta e tem a classe de erro', async () => {
    const { el, host, settle } = await render();
    host.kind.set('error');
    await settle();
    expect(el.getAttribute('role')).toBe('alert');
    expect(el.textContent).toContain('Erro: Algo aconteceu.');
    expect(el.classList.contains('notice--error')).toBe(true);
  });

  it('ok é status com prefixo próprio', async () => {
    const { el, host, settle } = await render();
    host.kind.set('ok');
    await settle();
    expect(el.getAttribute('role')).toBe('status');
    expect(el.textContent).toContain('Pronto: ');
  });
});
