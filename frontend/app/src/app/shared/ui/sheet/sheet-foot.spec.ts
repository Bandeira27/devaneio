import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvSheetFoot } from './sheet-foot';

@Component({
  imports: [DvSheetFoot],
  template:
    '<dv-sheet-foot><button type="button">Voltar</button><button type="button">Ir</button></dv-sheet-foot>',
})
class Host {}

describe('DvSheetFoot', () => {
  it('leva a classe do rodapé e mantém os botões na ordem em que foram escritos', async () => {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const foot = (fixture.nativeElement as HTMLElement).querySelector('dv-sheet-foot');
    expect(foot?.classList.contains('dv-sheet__foot')).toBe(true);
    expect([...(foot?.querySelectorAll('button') ?? [])].map((b) => b.textContent)).toEqual([
      'Voltar',
      'Ir',
    ]);
  });
});
