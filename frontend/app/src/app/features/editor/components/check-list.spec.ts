import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { CheckList } from './check-list';

@Component({
  imports: [CheckList],
  template: `<dv-check-list
    legend="Daqui se vai para"
    hint="Marque."
    [options]="options"
    [(selected)]="selected"
  />`,
})
class Host {
  readonly selected = signal<readonly string[]>(['b']);
  options = [
    { value: 'a', label: 'Vila' },
    { value: 'b', label: 'Floresta' },
  ];
}

describe('CheckList', () => {
  async function render() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    return {
      fixture,
      el,
      host: fixture.componentInstance,
      boxes: () => Array.from(el.querySelectorAll<HTMLInputElement>('input')),
    };
  }

  it('é um grupo com legenda e uma caixa nativa por opção, com as marcadas já marcadas', async () => {
    const { el, boxes } = await render();
    expect(el.querySelector('fieldset legend')?.textContent).toBe('Daqui se vai para');
    expect(el.textContent).toContain('Marque.');
    expect(boxes().map((b) => b.checked)).toEqual([false, true]);
  });

  it('marcar e desmarcar muda a lista de duas vias', async () => {
    const { fixture, boxes, host } = await render();
    boxes()[0]?.click();
    await fixture.whenStable();
    expect(host.selected()).toEqual(['b', 'a']);
    boxes()[1]?.click();
    await fixture.whenStable();
    expect(host.selected()).toEqual(['a']);
  });
});
