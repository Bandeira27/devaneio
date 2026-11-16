import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvField } from './field';
import { DvInput } from './input';

@Component({
  imports: [DvField, DvInput],
  template: `
    <dv-field label="Nome" [hint]="hint()" [error]="error()">
      <input dvInput type="text" />
    </dv-field>
  `,
})
class Host {
  readonly hint = signal('Como os outros vão te chamar.');
  readonly error = signal('');
}

describe('DvField', () => {
  async function render(): Promise<{
    root: HTMLElement;
    input: HTMLInputElement;
    host: Host;
    settle: () => Promise<void>;
  }> {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    return {
      root,
      host: fixture.componentInstance,
      input: root.querySelector('input') as HTMLInputElement,
      settle: () => fixture.whenStable(),
    };
  }

  it('liga o rótulo ao campo pelo id', async () => {
    const { root, input } = await render();
    const label = root.querySelector('label');
    expect(label?.textContent?.trim()).toBe('Nome');
    expect(input.id).toMatch(/^dv-input-\d+$/);
    expect(label?.getAttribute('for')).toBe(input.id);
  });

  it('cada campo tem um id próprio', async () => {
    const a = await render();
    const b = await render();
    expect(a.input.id).not.toBe(b.input.id);
  });

  it('a dica descreve o campo', async () => {
    const { root, input } = await render();
    const hint = root.querySelector('.field__hint');
    expect(hint?.textContent).toBe('Como os outros vão te chamar.');
    expect(input.getAttribute('aria-describedby')).toBe(hint?.id);
    expect(input.hasAttribute('aria-invalid')).toBe(false);
  });

  it('o erro aparece como alerta, marca o campo como inválido e entra na descrição', async () => {
    const { root, input, host, settle } = await render();
    host.error.set('Dê um nome.');
    await settle();
    const error = root.querySelector('.field__error');
    expect(error?.getAttribute('role')).toBe('alert');
    expect(error?.textContent).toBe('Dê um nome.');
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.getAttribute('aria-describedby')?.split(' ')).toContain(error?.id);
  });

  it('o erro some e o campo volta a válido quando o erro é limpo', async () => {
    const { root, input, host, settle } = await render();
    host.error.set('x');
    await settle();
    host.error.set('');
    await settle();
    expect(root.querySelector('.field__error')).toBeNull();
    expect(input.hasAttribute('aria-invalid')).toBe(false);
  });

  it('sem dica nem erro o campo não tem descrição', async () => {
    const { input, host, settle } = await render();
    host.hint.set('');
    await settle();
    expect(input.hasAttribute('aria-describedby')).toBe(false);
  });
});
