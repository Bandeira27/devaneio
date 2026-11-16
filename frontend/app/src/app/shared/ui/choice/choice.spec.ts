import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvChoice, type ChoiceOption } from './choice';

@Component({
  imports: [DvChoice],
  template: `<dv-choice legend="Dificuldade" [options]="options" [(value)]="value" />`,
})
class Host {
  readonly value = signal('normal');
  options: ChoiceOption[] = [
    { value: 'facil', label: 'Fácil' },
    { value: 'normal', label: 'Normal', detail: 'O padrão' },
    { value: 'dificil', label: 'Difícil' },
  ];
}

describe('DvChoice', () => {
  async function render() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const radios = () => Array.from(el.querySelectorAll<HTMLInputElement>('input[type=radio]'));
    return { fixture, el, radios, host: fixture.componentInstance };
  }

  it('é um grupo de rádios nativos com legenda, todos com o mesmo nome', async () => {
    const { el, radios } = await render();
    expect(el.querySelector('fieldset legend')?.textContent).toBe('Dificuldade');
    expect(radios().length).toBe(3);
    expect(new Set(radios().map((r) => r.name)).size).toBe(1);
  });

  it('marca a opção do valor e mostra a linha de apoio', async () => {
    const { el, radios } = await render();
    expect(radios().map((r) => r.checked)).toEqual([false, true, false]);
    expect(el.textContent).toContain('O padrão');
    expect(el.querySelector('.option--selected')?.textContent).toContain('Normal');
  });

  it('escolher uma opção muda o valor do pai', async () => {
    const { fixture, radios, host } = await render();
    const hard = radios()[2] as HTMLInputElement;
    hard.checked = true;
    hard.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(host.value()).toBe('dificil');
  });

  it('dois grupos na mesma tela não se misturam (nomes diferentes)', async () => {
    const a = TestBed.createComponent(Host);
    const b = TestBed.createComponent(Host);
    await a.whenStable();
    await b.whenStable();
    const name = (f: typeof a) =>
      (f.nativeElement as HTMLElement).querySelector<HTMLInputElement>('input')?.name;
    expect(name(a)).not.toBe(name(b));
  });
});
