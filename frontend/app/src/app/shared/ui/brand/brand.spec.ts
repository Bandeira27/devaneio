import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvBrand, type BrandSize } from './brand';

@Component({ imports: [DvBrand], template: `<dv-brand [size]="size()" />` })
class Host {
  readonly size = signal<BrandSize>('md');
}

describe('DvBrand', () => {
  async function render() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    return {
      fixture,
      el: (fixture.nativeElement as HTMLElement).querySelector('dv-brand') as HTMLElement,
    };
  }

  it('o nome é o que se lê; o selo é decoração escondida do leitor de tela', async () => {
    const { el } = await render();
    expect(el.querySelector('.word')?.textContent).toBe('Devaneio');
    expect(el.querySelector('.seal')?.getAttribute('aria-hidden')).toBe('true');
  });

  it('o tamanho vira classe e muda com a entrada', async () => {
    const { fixture, el } = await render();
    expect(el.classList.contains('brand--md')).toBe(true);
    fixture.componentInstance.size.set('lg');
    await fixture.whenStable();
    expect(el.classList.contains('brand--lg')).toBe(true);
  });
});
