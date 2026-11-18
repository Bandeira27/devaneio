import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { LinesField } from './lines-field';

@Component({
  imports: [LinesField],
  template: `<dv-lines-field label="Notas" [(lines)]="lines" />`,
})
class Host {
  readonly lines = signal<readonly string[]>(['uma', 'duas']);
}

describe('LinesField', () => {
  async function render() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const area = (fixture.nativeElement as HTMLElement).querySelector(
      'textarea',
    ) as HTMLTextAreaElement;
    return { fixture, area, host: fixture.componentInstance };
  }

  it('mostra uma linha por item', async () => {
    const { area } = await render();
    expect(area.value).toBe('uma\nduas');
  });

  it('digitar vira a lista (sem linhas em branco), e a linha em branco que se acabou de abrir não some', async () => {
    const { fixture, area, host } = await render();
    area.value = 'uma\nduas\n';
    area.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    expect(host.lines()).toEqual(['uma', 'duas']);
    expect(area.value).toBe('uma\nduas\n'); // o Enter que o autor acabou de dar continua lá
  });

  it('uma troca de fora da lista atualiza a caixa', async () => {
    const { fixture, area, host } = await render();
    host.lines.set(['nova']);
    await fixture.whenStable();
    expect(area.value).toBe('nova');
  });

  it('o erro não é anunciado como alerta (fica ligado ao campo)', async () => {
    const fixture = TestBed.createComponent(LinesField);
    fixture.componentRef.setInput('label', 'Notas');
    fixture.componentRef.setInput('error', 'Algo errado.');
    await fixture.whenStable();
    const error = (fixture.nativeElement as HTMLElement).querySelector('.field__error');
    expect(error?.getAttribute('role')).toBeNull();
    expect(error?.textContent?.trim()).toBe('Algo errado.');
  });
});
