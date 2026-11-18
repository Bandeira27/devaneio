import { TestBed } from '@angular/core/testing';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { AttackSheet, type AttackSheetData } from './attack-sheet';

function mount(data: AttackSheetData) {
  const close = vi.fn();
  TestBed.configureTestingModule({
    providers: [
      { provide: SHEET_DATA, useValue: data },
      { provide: SheetRef, useValue: { close } },
    ],
  });
  const fixture = TestBed.createComponent(AttackSheet);
  fixture.detectChanges();
  return { el: fixture.nativeElement as HTMLElement, close, fixture };
}

const DATA: AttackSheetData = {
  weapons: [{ id: 'punhos', name: 'Punhos', damage: '1d3', attribute: 'FOR' } as never],
  targets: [
    { id: 'gato', name: 'Gato', hp: 3, maxHp: 3, hostile: false },
    { id: 'lobo', name: 'Lobo', hp: 5, maxHp: 8, hostile: true },
  ],
  modifiers: [],
};

describe('AttackSheet', () => {
  it('o primeiro alvo hostil já vem marcado, com a vida no detalhe', () => {
    const { el } = mount(DATA);
    const radios = Array.from(el.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
    expect(radios.find((r) => r.checked)?.value).toBe('lobo');
    expect(el.textContent).toContain('5/8 de vida · hostil');
  });

  it('o botão do rodapé diz quem será atacado, avisa o custo e devolve o comando', () => {
    const { el, close } = mount(DATA);
    expect(el.textContent).toContain('Gasta a sua ação.');
    const attack = el.querySelector('.dv-sheet__foot .dv-button--primary') as HTMLButtonElement;
    expect(attack.textContent?.trim()).toBe('Atacar Lobo');
    attack.click();
    expect(close).toHaveBeenCalledWith('atacar punhos lobo');
  });

  it('Cancelar fecha sem atacar', () => {
    const { el, close } = mount(DATA);
    (
      el.querySelector('.dv-sheet__foot .dv-button:not(.dv-button--primary)') as HTMLButtonElement
    ).click();
    expect(close).toHaveBeenCalledWith();
  });
});
