import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvSelect, type SelectOption } from './select';

@Component({
  imports: [DvSelect],
  template: `<dv-select
    label="Local de partida"
    hint="Onde o grupo começa."
    [error]="error()"
    [options]="options"
    [(value)]="value"
  />`,
})
class Host {
  readonly value = signal('floresta');
  readonly error = signal('');
  options: SelectOption[] = [
    { value: '', label: '(nenhum)' },
    { value: 'vila', label: 'Vila' },
    { value: 'floresta', label: 'Floresta' },
  ];
}

describe('DvSelect', () => {
  async function render() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const select = el.querySelector('select') as HTMLSelectElement;
    return { fixture, el, select, host: fixture.componentInstance };
  }

  it('é um select nativo com rótulo e dica ligados, e a opção do valor marcada', async () => {
    const { el, select } = await render();
    expect(el.querySelector('label')?.textContent).toBe('Local de partida');
    expect(el.querySelector('label')?.getAttribute('for')).toBe(select.id);
    expect(select.getAttribute('aria-describedby')).toContain('-hint');
    expect(select.value).toBe('floresta');
    expect(Array.from(select.options).map((o) => o.textContent?.trim())).toEqual([
      '(nenhum)',
      'Vila',
      'Floresta',
    ]);
  });

  it('escolher uma opção muda o valor de duas vias, inclusive para "nenhum"', async () => {
    const { fixture, select, host } = await render();
    select.value = 'vila';
    select.dispatchEvent(new Event('change'));
    await fixture.whenStable();
    expect(host.value()).toBe('vila');
    select.value = '';
    select.dispatchEvent(new Event('change'));
    expect(host.value()).toBe('');
  });

  it('o erro aparece em texto e marca o campo como inválido', async () => {
    const { fixture, el, select, host } = await render();
    host.error.set('Esse local não existe.');
    await fixture.whenStable();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('Esse local não existe.');
    expect(select.getAttribute('aria-invalid')).toBe('true');
  });
});
