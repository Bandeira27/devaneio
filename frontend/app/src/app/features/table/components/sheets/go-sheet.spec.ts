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

describe('GoSheet', () => {
  it('sem destino escolhido mostra a lista; tocar num destino pede a confirmação', () => {
    const { el, close, fixture } = mount({ exits: EXITS });
    const buttons = Array.from(el.querySelectorAll('.dv-stack button')) as HTMLButtonElement[];
    expect(buttons.map((b) => b.textContent?.trim())).toEqual(['Floresta', 'Pântano']);
    buttons[1]?.click();
    fixture.detectChanges();
    expect(close).not.toHaveBeenCalled();
    expect(el.querySelector('strong')?.textContent).toBe('Pântano');
  });

  it('com destino pré-escolhido (saída tocada na cena) abre direto na confirmação', () => {
    const { el, close, fixture } = mount({ exits: EXITS, preselect: 'pantano' });
    expect(el.querySelector('strong')?.textContent).toBe('Pântano');
    (el.querySelector('.dv-button--primary') as HTMLButtonElement).click(); // Confirmar
    expect(close).toHaveBeenCalledWith('ir pantano');
    fixture.destroy();
  });

  it('um destino pré-escolhido que não existe cai na lista', () => {
    const { el } = mount({ exits: EXITS, preselect: 'nao-existe' });
    expect(el.querySelector('strong')).toBeNull();
    expect(el.querySelectorAll('.dv-stack button').length).toBe(2);
  });
});
