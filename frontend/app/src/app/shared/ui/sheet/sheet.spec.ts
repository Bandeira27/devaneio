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
});
