import { Component, inject } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { SHEET_DATA, Sheet, SheetRef } from './sheet';

@Component({
  template: `
    <h2>{{ data }}</h2>
    <button id="a" type="button" (click)="ref.close('ir floresta')">Floresta</button>
    <button id="b" type="button" (click)="ref.close()">Nada</button>
  `,
})
class Content {
  protected readonly data = inject(SHEET_DATA) as string;
  protected readonly ref = inject<SheetRef<string>>(SheetRef);
}

describe('Sheet', () => {
  const panel = (): HTMLElement | null => document.querySelector('.dv-sheet');
  const tick = (): Promise<void> => new Promise((resolve) => setTimeout(resolve, 0));

  afterEach(() => {
    document.querySelectorAll('.cdk-overlay-container').forEach((el) => el.remove());
  });

  it('abre a folha com os dados e o nome acessível, e resolve com o resultado', async () => {
    const result = TestBed.inject(Sheet).open<string>(Content, {
      label: 'Ir para',
      data: 'Saídas',
    });
    await tick();
    expect(panel()?.querySelector('h2')?.textContent).toBe('Saídas');
    expect(document.querySelector('[role="dialog"]')?.getAttribute('aria-label')).toBe('Ir para');
    (panel()?.querySelector('#a') as HTMLButtonElement).click();
    expect(await result).toBe('ir floresta');
    await tick();
    expect(panel()).toBeNull();
  });

  it('fechada sem escolher resolve com undefined', async () => {
    const result = TestBed.inject(Sheet).open<string>(Content, { label: 'x', data: 'y' });
    await tick();
    (panel()?.querySelector('#b') as HTMLButtonElement).click();
    expect(await result).toBeUndefined();
  });

  it('fecha com Esc', async () => {
    const result = TestBed.inject(Sheet).open(Content, { label: 'x', data: 'y' });
    await tick();
    const escape = new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true });
    Object.defineProperty(escape, 'keyCode', { value: 27 }); // o jsdom ignora o keyCode do construtor
    (document.querySelector('.dv-sheet') as HTMLElement).dispatchEvent(escape);
    expect(await result).toBeUndefined();
  });

  it('fecha com o clique no fundo', async () => {
    const result = TestBed.inject(Sheet).open(Content, { label: 'x', data: 'y' });
    await tick();
    (document.querySelector('.dv-sheet-backdrop') as HTMLElement).click();
    expect(await result).toBeUndefined();
  });

  it('ancora o painel no pé da tela', async () => {
    void TestBed.inject(Sheet).open(Content, { label: 'x', data: 'y' });
    await tick();
    const wrapper = panel()?.closest('.cdk-global-overlay-wrapper') as HTMLElement;
    expect(wrapper).not.toBeNull();
    expect(wrapper.style.justifyContent).toBe('center');
  });

  it('com animação de saída: marca como saindo, espera o fim e só então fecha', async () => {
    const styles = vi
      .spyOn(window, 'getComputedStyle')
      .mockReturnValue({ animationDuration: '0.2s' } as CSSStyleDeclaration);
    try {
      let closed = false;
      const result = TestBed.inject(Sheet)
        .open<string>(Content, { label: 'x', data: 'y' })
        .then((value) => {
          closed = true;
          return value;
        });
      await tick();
      (panel()?.querySelector('#a') as HTMLButtonElement).click();
      expect(panel()?.classList.contains('dv-sheet--leaving')).toBe(true);
      expect(document.querySelector('.dv-sheet-backdrop--leaving')).not.toBeNull();
      expect(closed).toBe(false); // ainda na animação
      panel()?.dispatchEvent(new Event('animationend'));
      expect(await result).toBe('ir floresta');
    } finally {
      styles.mockRestore();
    }
  });

  it('o fim da animação de um filho não fecha a folha: só o da própria folha', async () => {
    const styles = vi
      .spyOn(window, 'getComputedStyle')
      .mockReturnValue({ animationDuration: '0.2s' } as CSSStyleDeclaration);
    try {
      let closed = false;
      const result = TestBed.inject(Sheet)
        .open<string>(Content, { label: 'x', data: 'y' })
        .then((value) => {
          closed = true;
          return value;
        });
      await tick();
      (panel()?.querySelector('#a') as HTMLButtonElement).click();
      panel()
        ?.querySelector('h2')
        ?.dispatchEvent(new Event('animationend', { bubbles: true })); // de um filho
      await tick();
      expect(closed).toBe(false);
      panel()?.dispatchEvent(new Event('animationend'));
      expect(await result).toBe('ir floresta');
    } finally {
      styles.mockRestore();
    }
  });

  it('se o fim da animação não vier, um limite de tempo fecha a folha', async () => {
    vi.useFakeTimers();
    const styles = vi
      .spyOn(window, 'getComputedStyle')
      .mockReturnValue({ animationDuration: '0.2s' } as CSSStyleDeclaration);
    try {
      const result = TestBed.inject(Sheet).open<string>(Content, { label: 'x', data: 'y' });
      await vi.advanceTimersByTimeAsync(0);
      (panel()?.querySelector('#b') as HTMLButtonElement).click();
      await vi.advanceTimersByTimeAsync(400);
      expect(await result).toBeUndefined();
    } finally {
      styles.mockRestore();
      vi.useRealTimers();
    }
  });

  it('fechar duas vezes seguidas só vale a primeira', async () => {
    const result = TestBed.inject(Sheet).open<string>(Content, { label: 'x', data: 'y' });
    await tick();
    (panel()?.querySelector('#a') as HTMLButtonElement).click();
    (panel()?.querySelector('#b') as HTMLButtonElement)?.click();
    expect(await result).toBe('ir floresta');
  });
});
