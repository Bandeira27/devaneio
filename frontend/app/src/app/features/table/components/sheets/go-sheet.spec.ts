import { TestBed } from '@angular/core/testing';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { GoSheet, type GoSheetData } from './go-sheet';

function mount(data: GoSheetData) {
  const close = vi.fn();
  TestBed.configureTestingModule({
    providers: [
      { provide: SHEET_DATA, useValue: data },
      { provide: SheetRef, useValue: { close } },
    ],
  });
  const fixture = TestBed.createComponent(GoSheet);
  fixture.detectChanges();
  return { el: fixture.nativeElement as HTMLElement, close, fixture };
}

const EXITS = [
  { id: 'floresta', name: 'Floresta' },
  { id: 'pantano', name: 'Pântano' },
];

function primary(el: HTMLElement): HTMLButtonElement {
  return el.querySelector('.dv-sheet__foot .dv-button--primary') as HTMLButtonElement;
}

describe('GoSheet', () => {
  it('abre com a primeira saída marcada e o botão diz para onde vai', () => {
    const { el } = mount({ exits: EXITS });
    const options = Array.from(el.querySelectorAll('.option .label')).map((o) => o.textContent);
    expect(options).toEqual(['Floresta', 'Pântano']);
    expect(primary(el).textContent?.trim()).toBe('Ir para Floresta');
  });

  it('escolher outro destino troca o botão e confirmar devolve a linha de comando', () => {
    const { el, close, fixture } = mount({ exits: EXITS });
    (el.querySelectorAll('input[type="radio"]')[1] as HTMLInputElement).click();
    fixture.detectChanges();
    expect(primary(el).textContent?.trim()).toBe('Ir para Pântano');
    expect(close).not.toHaveBeenCalled();
    primary(el).click();
    expect(close).toHaveBeenCalledWith('ir pantano');
  });

  it('o destino tocado na cena já vem marcado', () => {
    const { el } = mount({ exits: EXITS, preselect: 'pantano' });
    expect(primary(el).textContent?.trim()).toBe('Ir para Pântano');
  });

  it('um destino pré-escolhido que não existe cai na primeira saída', () => {
    const { el } = mount({ exits: EXITS, preselect: 'nao-existe' });
    expect(primary(el).textContent?.trim()).toBe('Ir para Floresta');
  });

  it('Cancelar fecha sem escolher', () => {
    const { el, close } = mount({ exits: EXITS });
    const cancel = el.querySelector('.dv-sheet__foot .dv-button:not(.dv-button--primary)');
    (cancel as HTMLButtonElement).click();
    expect(close).toHaveBeenCalledWith();
  });

  it('sem saídas só avisa e oferece Fechar', () => {
    const { el } = mount({ exits: [] });
    expect(el.textContent).toContain('Não há saídas daqui.');
    expect(el.querySelector('input[type="radio"]')).toBeNull();
    expect(el.querySelector('.dv-sheet__foot .dv-button')?.textContent?.trim()).toBe('Fechar');
  });
});
