import { Component, ElementRef, viewChild } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { publishDockHeight } from './dock-height';

@Component({ template: '<div #dock></div>' })
class Host {
  readonly dock = viewChild<ElementRef<HTMLElement>>('dock');

  constructor() {
    publishDockHeight(this.dock);
  }
}

class FakeObserver {
  static last: FakeObserver | undefined;
  disconnected = false;
  observed: Element[] = [];
  constructor(readonly callback: () => void) {
    FakeObserver.last = this;
  }
  observe(target: Element): void {
    this.observed.push(target);
  }
  disconnect(): void {
    this.disconnected = true;
  }
}

describe('publishDockHeight', () => {
  const read = (): string => document.documentElement.style.getPropertyValue('--dv-dock-height');

  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', FakeObserver);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.documentElement.style.removeProperty('--dv-dock-height');
  });

  async function mount(height: number) {
    const fixture = TestBed.createComponent(Host);
    const dock = (fixture.nativeElement as HTMLElement).querySelector('div') as HTMLElement;
    Object.defineProperty(dock, 'offsetHeight', { value: height, configurable: true });
    await fixture.whenStable();
    return fixture;
  }

  it('no celular publica a altura da barra e a atualiza quando ela muda', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: false })); // celular
    const fixture = await mount(120);
    expect(read()).toBe('120px');
    expect(FakeObserver.last?.observed.length).toBe(1); // observa a barra
    const dock = (fixture.nativeElement as HTMLElement).querySelector('div') as HTMLElement;
    Object.defineProperty(dock, 'offsetHeight', { value: 80, configurable: true });
    FakeObserver.last?.callback();
    expect(read()).toBe('80px');
  });

  it('na tela larga a barra não cobre nada: altura zero', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    await mount(120);
    expect(read()).toBe('0px');
  });

  it('ao destruir, para de observar e limpa a altura', async () => {
    const fixture = await mount(120);
    fixture.destroy();
    expect(FakeObserver.last?.disconnected).toBe(true);
    expect(read()).toBe('');
  });
});
