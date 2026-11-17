import { TestBed } from '@angular/core/testing';
import { SHEET_DATA, SheetRef } from '../sheet/sheet';
import { ConfirmSheet, type ConfirmSheetData } from './confirm-sheet';

function mount(data: ConfirmSheetData) {
  const close = vi.fn();
  TestBed.configureTestingModule({
    providers: [
      { provide: SHEET_DATA, useValue: data },
      { provide: SheetRef, useValue: { close } },
    ],
  });
  const fixture = TestBed.createComponent(ConfirmSheet);
  fixture.detectChanges();
  return { el: fixture.nativeElement as HTMLElement, close };
}

describe('ConfirmSheet', () => {
  const data: ConfirmSheetData = {
    title: 'Fim do turno',
    text: 'Encerra o turno.',
    action: 'Encerrar',
  };

  it('só confirma no botão primário e "Voltar" fecha sem nada', () => {
    const { el, close } = mount(data);
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
