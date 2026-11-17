import { TestBed } from '@angular/core/testing';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { AmountSheet, type AmountSheetData } from './amount-sheet';
import { ConfirmSheet, type ConfirmSheetData } from './confirm-sheet';

function mount<T>(component: new () => T, data: object) {
  const close = vi.fn();
  TestBed.configureTestingModule({
    providers: [
      { provide: SHEET_DATA, useValue: data },
      { provide: SheetRef, useValue: { close } },
    ],
  });
  const fixture = TestBed.createComponent(component);
  fixture.detectChanges();
  return { el: fixture.nativeElement as HTMLElement, close, fixture };
}

const DATA: AmountSheetData = {
  verb: 'ferir',
  targets: [
    { id: 'bia', name: 'Bia', kind: 'character' },
    { id: 'ferreiro', name: 'Bram', kind: 'npc' },
  ],
};

describe('AmountSheet', () => {
  it('lista os alvos com o que são e devolve a linha de ferir', () => {
    const { el, close } = mount(AmountSheet, DATA);
    expect(el.textContent).toContain('Personagem');
    expect(el.textContent).toContain('NPC');
    el.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }));
    expect(close).toHaveBeenCalledWith('ferir bia 1');
  });

  it('curar com a fonte entre aspas', () => {
    const { el, close, fixture } = mount(AmountSheet, { ...DATA, verb: 'curar' });
    const source = el.querySelector<HTMLInputElement>('input[type="text"]') as HTMLInputElement;
    source.value = 'poção';
    source.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    el.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }));
    expect(close).toHaveBeenCalledWith('curar bia 1 "poção"');
  });

  it('sem alvo diz que não há ninguém', () => {
    const { el } = mount(AmountSheet, { ...DATA, targets: [] });
    expect(el.textContent).toContain('Não há ninguém para ferir.');
    expect(el.querySelector('form')).toBeNull();
  });
});

describe('ConfirmSheet', () => {
  const data: ConfirmSheetData = {
    title: 'Fim do turno',
    text: 'Encerra o turno.',
    action: 'Encerrar',
  };

  it('só confirma no botão primário e "Voltar" fecha sem nada', () => {
    const { el, close } = mount(ConfirmSheet, data);
    expect(el.textContent).toContain('Encerra o turno.');
    const [back, confirm] = Array.from(
      el.querySelectorAll<HTMLButtonElement>('.dv-sheet__foot button'),
    );
    back?.click();
    expect(close).toHaveBeenLastCalledWith();
    confirm?.click();
    expect(close).toHaveBeenLastCalledWith(true);
  });
});
