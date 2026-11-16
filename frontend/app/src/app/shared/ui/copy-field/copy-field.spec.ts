import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvCopyField } from './copy-field';

@Component({
  imports: [DvCopyField],
  template: `<dv-copy-field
    label="Link do convite"
    text="http://192.168.0.5:8765/#/entrar/abc/def"
  />`,
})
class Host {}

describe('DvCopyField', () => {
  async function render(): Promise<{
    root: HTMLElement;
    input: HTMLInputElement;
    button: HTMLButtonElement;
    status: HTMLElement;
    settle: () => Promise<void>;
  }> {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    return {
      root,
      input: root.querySelector('input') as HTMLInputElement,
      button: root.querySelector('button') as HTMLButtonElement,
      status: root.querySelector('.copy__status') as HTMLElement,
      settle: () => fixture.whenStable(),
    };
  }

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('mostra o texto num campo só de leitura, ligado ao rótulo', async () => {
    const { root, input } = await render();
    expect(input.readOnly).toBe(true);
    expect(input.value).toBe('http://192.168.0.5:8765/#/entrar/abc/def');
    expect(root.querySelector('label')?.getAttribute('for')).toBe(input.id);
  });

  it('copia pela área de transferência quando ela existe', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    const { button, status, settle } = await render();
    button.click();
    await vi.waitFor(() =>
      expect(writeText).toHaveBeenCalledWith('http://192.168.0.5:8765/#/entrar/abc/def'),
    );
    await settle();
    expect(status.textContent?.trim()).toBe('Copiado.');
    vi.unstubAllGlobals();
  });

  it('cai para execCommand quando a área de transferência não existe (HTTP na rede local)', async () => {
    vi.stubGlobal('navigator', {});
    const exec = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, 'execCommand', { value: exec, configurable: true });
    const { button, status, settle } = await render();
    button.click();
    await vi.waitFor(() => expect(exec).toHaveBeenCalledWith('copy'));
    await settle();
    expect(status.textContent?.trim()).toBe('Copiado.');
    vi.unstubAllGlobals();
  });

  it('se nada copiar, pede para copiar à mão e deixa o texto selecionado', async () => {
    vi.stubGlobal('navigator', {});
    Object.defineProperty(document, 'execCommand', { value: () => false, configurable: true });
    const { button, input, status, settle } = await render();
    const select = vi.spyOn(input, 'select');
    button.click();
    await vi
      .waitFor(() => expect(status.textContent).toContain('copie à mão'), { timeout: 2000 })
      .catch(async () => {
        await settle();
      });
    await settle();
    expect(select).toHaveBeenCalled();
    expect(status.textContent).toContain('copie à mão');
    vi.unstubAllGlobals();
  });

  it('seleciona o texto ao focar o campo', async () => {
    const { input } = await render();
    const select = vi.spyOn(input, 'select');
    input.dispatchEvent(new Event('focus'));
    expect(select).toHaveBeenCalled();
  });
});
