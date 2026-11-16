import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvSheetHead } from './sheet-head';
import { SheetRef } from './sheet';

@Component({ imports: [DvSheetHead], template: '<dv-sheet-head title="Ir para" />' })
class Host {}

describe('DvSheetHead', () => {
  it('mostra o título e o botão Fechar fecha a folha sem escolher nada', async () => {
    const close = vi.fn();
    TestBed.configureTestingModule({ providers: [{ provide: SheetRef, useValue: { close } }] });
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('h2')?.textContent).toBe('Ir para');
    (root.querySelector('button') as HTMLButtonElement).click();
    expect(close).toHaveBeenCalledWith();
  });
});
