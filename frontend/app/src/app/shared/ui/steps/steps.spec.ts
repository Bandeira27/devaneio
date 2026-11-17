import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvSteps } from './steps';

@Component({
  imports: [DvSteps],
  template: `<dv-steps [steps]="['Mesa', 'Personagem', 'Jogar']" [current]="current()" />`,
})
class Host {
  readonly current = signal(1);
}

describe('DvSteps', () => {
  async function render() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const el = (fixture.nativeElement as HTMLElement).querySelector('dv-steps') as HTMLElement;
    return { fixture, el };
  }

  it('é uma lista nomeada; só o passo atual leva aria-current e diz "(agora)"', async () => {
    const { el } = await render();
    expect(el.querySelector('ol')?.getAttribute('aria-label')).toBe('Passos');
    const items = Array.from(el.querySelectorAll('li'));
    expect(items.map((li) => li.getAttribute('aria-current'))).toEqual([null, 'step', null]);
    expect(items[1]?.textContent).toContain('Personagem');
    expect(items[1]?.textContent).toContain('(agora)');
    expect(items[0]?.textContent).not.toContain('(agora)');
  });

  it('os passos antes do atual aparecem como feitos, e mudam com a entrada', async () => {
    const { fixture, el } = await render();
    expect(el.querySelectorAll('li.done').length).toBe(1);
    fixture.componentInstance.current.set(2);
    await fixture.whenStable();
    expect(el.querySelectorAll('li.done').length).toBe(2);
    expect(el.querySelector('li.current')?.textContent).toContain('Jogar');
  });
});
