import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvButton } from './button';

@Component({
  imports: [DvButton],
  template: `
    <button dvButton type="button">Discreto</button>
    <button dvButton="primary" type="submit">Principal</button>
    <a dvButton="primary" href="#/x">Link</a>
  `,
})
class Host {}

@Component({
  imports: [DvButton],
  template: `<button
    dvButton
    type="button"
    [dvBlocked]="blocked()"
    [dvLoading]="loading()"
    (click)="clicks = clicks + 1"
  >
    Ir
  </button>`,
})
class StatesHost {
  readonly blocked = signal(false);
  readonly loading = signal(false);
  clicks = 0;
}

describe('DvButton', () => {
  it('põe a classe base e a variante no botão e no link nativos', async () => {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const [ghost, primary, link] = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('[dvbutton]'),
    );
    expect(ghost?.classList.contains('dv-button')).toBe(true);
    expect(ghost?.classList.contains('dv-button--primary')).toBe(false);
    expect(primary?.classList.contains('dv-button--primary')).toBe(true);
    expect(link?.classList.contains('dv-button--primary')).toBe(true);
    expect(primary?.getAttribute('type')).toBe('submit');
    expect(link?.tagName).toBe('A');
  });

  describe('estados', () => {
    async function render() {
      const fixture = TestBed.createComponent(StatesHost);
      await fixture.whenStable();
      const button = (fixture.nativeElement as HTMLElement).querySelector(
        'button',
      ) as HTMLButtonElement;
      return { fixture, button, host: fixture.componentInstance };
    }

    it('livre: sem aria-disabled nem aria-busy, e o clique passa', async () => {
      const { button, host } = await render();
      expect(button.hasAttribute('aria-disabled')).toBe(false);
      expect(button.hasAttribute('aria-busy')).toBe(false);
      button.click();
      expect(host.clicks).toBe(1);
    });

    it('bloqueado: aria-disabled, continua focável e o clique não passa', async () => {
      const { fixture, button, host } = await render();
      host.blocked.set(true);
      await fixture.whenStable();
      expect(button.getAttribute('aria-disabled')).toBe('true');
      expect(button.disabled).toBe(false); // continua no foco, para o motivo poder ser lido
      button.click();
      expect(host.clicks).toBe(0);
    });

    it('em envio: aria-busy e aria-disabled, ponto de pendência e sem clique', async () => {
      const { fixture, button, host } = await render();
      host.loading.set(true);
      await fixture.whenStable();
      expect(button.getAttribute('aria-busy')).toBe('true');
      expect(button.getAttribute('aria-disabled')).toBe('true');
      expect(button.classList.contains('dv-button--loading')).toBe(true);
      button.click();
      expect(host.clicks).toBe(0);
    });
  });
});
