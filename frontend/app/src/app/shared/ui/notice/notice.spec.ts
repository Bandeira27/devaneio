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

@Component({
  imports: [DvNotice],
  template: `<dv-notice dismissible (dismissed)="count = count + 1">Aviso</dv-notice>`,
})
class DismissHost {
  count = 0;
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

  it('aviso de informação é status, sem prefixo, e tem ícone escondido do leitor de tela', async () => {
    const { el } = await render();
    expect(el.getAttribute('role')).toBe('status');
    expect(el.textContent?.trim()).toBe('Algo aconteceu.');
    expect(el.querySelector('dv-icon')?.getAttribute('aria-hidden')).toBe('true');
    expect(el.classList.contains('notice--info')).toBe(true);
  });

  it('atenção é status com prefixo próprio', async () => {
    const { el, host, settle } = await render();
    host.kind.set('warn');
    await settle();
    expect(el.getAttribute('role')).toBe('status');
    expect(el.textContent).toContain('Atenção: ');
  });

  it('dispensável: o botão tem nome e avisa quem mostra o aviso', async () => {
    const fixture = TestBed.createComponent(DismissHost);
    await fixture.whenStable();
    const button = (fixture.nativeElement as HTMLElement).querySelector(
      'button',
    ) as HTMLButtonElement;
    expect(button.getAttribute('aria-label')).toBe('Dispensar o aviso');
    button.click();
    expect(fixture.componentInstance.count).toBe(1);
  });

  it('sem `dismissible` não há botão', async () => {
    const { el } = await render();
    expect(el.querySelector('button')).toBeNull();
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
