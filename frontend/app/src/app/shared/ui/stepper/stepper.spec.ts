import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvStepper } from './stepper';

@Component({
  imports: [DvStepper],
  template: `<dv-stepper
    label="Força"
    hint="O quanto você aguenta."
    [min]="1"
    [max]="5"
    [(value)]="value"
  />`,
})
class Host {
  readonly value = signal(2);
}

describe('DvStepper', () => {
  async function render(start = 2): Promise<{
    root: HTMLElement;
    host: Host;
    less: HTMLButtonElement;
    more: HTMLButtonElement;
    settle: () => Promise<void>;
  }> {
    const fixture = TestBed.createComponent(Host);
    fixture.componentInstance.value.set(start);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    return {
      root,
      host: fixture.componentInstance,
      less: root.querySelector('[aria-label="Diminuir Força"]') as HTMLButtonElement,
      more: root.querySelector('[aria-label="Aumentar Força"]') as HTMLButtonElement,
      settle: () => fixture.whenStable(),
    };
  }

  it('mostra o rótulo, a dica e o valor', async () => {
    const { root } = await render();
    expect(root.querySelector('.stepper__label')?.textContent).toBe('Força');
    expect(root.querySelector('.stepper__hint')?.textContent).toBe('O quanto você aguenta.');
    expect(root.querySelector('output')?.textContent).toBe('2');
  });

  it('sobe e desce com os botões e atualiza o valor do pai', async () => {
    const { host, less, more, settle, root } = await render();
    more.click();
    await settle();
    more.click();
    await settle();
    expect(host.value()).toBe(4);
    expect(root.querySelector('output')?.textContent).toBe('4');
    less.click();
    await settle();
    expect(host.value()).toBe(3);
  });

  it('não passa do máximo: o + desabilita', async () => {
    const { host, more, settle } = await render(5);
    expect(more.disabled).toBe(true);
    more.click();
    await settle();
    expect(host.value()).toBe(5);
  });

  it('não passa do mínimo: o − desabilita', async () => {
    const { host, less, settle } = await render(1);
    expect(less.disabled).toBe(true);
    less.click();
    await settle();
    expect(host.value()).toBe(1);
  });

  it('os botões têm nome acessível e o grupo é rotulado', async () => {
    const { root, less, more } = await render();
    expect(less.getAttribute('aria-label')).toBe('Diminuir Força');
    expect(more.getAttribute('aria-label')).toBe('Aumentar Força');
    expect(root.querySelector('[role="group"]')?.getAttribute('aria-labelledby')).toBe(
      'stepper-Força',
    );
  });
});
