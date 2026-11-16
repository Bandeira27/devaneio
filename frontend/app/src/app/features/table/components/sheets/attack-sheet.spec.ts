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

  it('atacar pede confirmação e só então devolve o comando; "Voltar" desfaz', () => {
    const { el, close, fixture } = mount(DATA);
    el.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }));
    fixture.detectChanges();
    expect(close).not.toHaveBeenCalled();
    expect(el.textContent).toContain('Atacar Lobo com Punhos. Gasta a sua ação.');
    (el.querySelector('.dv-sheet__foot button') as HTMLButtonElement).click(); // Voltar
    fixture.detectChanges();
    expect(el.querySelector('form')).not.toBeNull();
    el.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }));
    fixture.detectChanges();
    (el.querySelector('.dv-button--primary') as HTMLButtonElement).click();
    expect(close).toHaveBeenCalledWith('atacar punhos lobo');
  });
});
