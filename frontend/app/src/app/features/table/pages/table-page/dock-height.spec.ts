import { Component, ElementRef, viewChild } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { publishDockHeight, publishRailHeights } from './dock-height';

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

@Component({
  template: '<div #above><div #layout><div #side></div><div #dock></div></div></div>',
})
class RailHost {
  readonly side = viewChild<ElementRef<HTMLElement>>('side');
  readonly dock = viewChild<ElementRef<HTMLElement>>('dock');

  constructor() {
    publishRailHeights(this.side, this.dock);
  }
}

describe('publishRailHeights', () => {
  const read = (name: string): string => document.documentElement.style.getPropertyValue(name);
  const names = ['--dv-rail-top', '--dv-rail-side-height', '--dv-rail-dock-height'];

  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', FakeObserver);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    names.forEach((name) => document.documentElement.style.removeProperty(name));
  });

  async function mount(top: number) {
    const fixture = TestBed.createComponent(RailHost);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    const layout = (root.firstElementChild as HTMLElement).firstElementChild as HTMLElement;
    const [side, dock] = Array.from(layout.children) as HTMLElement[];
    Object.defineProperty(side, 'offsetHeight', { value: 400, configurable: true });
    Object.defineProperty(dock, 'offsetHeight', { value: 100, configurable: true });
    layout.getBoundingClientRect = () => ({ top }) as DOMRect;
    window.dispatchEvent(new Event('resize')); // o efeito já rodou: refaz a medida com as medidas combinadas
    await fixture.whenStable();
    return { fixture, layout };
  }

  it('na tela larga publica onde a lateral começa na página, e as alturas da cena e da barra', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    await mount(203);
    expect(read('--dv-rail-top')).toBe('203px');
    expect(read('--dv-rail-side-height')).toBe('400px');
    expect(read('--dv-rail-dock-height')).toBe('100px');
  });

  it('o topo é da página, não da janela: soma a rolagem atual', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    vi.spyOn(window, 'scrollY', 'get').mockReturnValue(80);
    await mount(123); // com a página rolada 80 px, a lateral aparece 80 px mais acima
    expect(read('--dv-rail-top')).toBe('203px');
  });

  it('refaz o topo quando a janela muda de tamanho e quando algo aparece acima da lateral', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    const { layout } = await mount(203);
    layout.getBoundingClientRect = () => ({ top: 260 }) as DOMRect; // um aviso entrou acima
    window.dispatchEvent(new Event('resize'));
    expect(read('--dv-rail-top')).toBe('260px');
    expect(FakeObserver.last?.observed.length).toBe(3); // cena, barra e o que fica acima da lateral
  });

  it('no celular não há lateral: tudo zero', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
    await mount(203);
    expect(read('--dv-rail-top')).toBe('0px');
    expect(read('--dv-rail-dock-height')).toBe('0px');
  });

  it('ao destruir, para de observar e limpa as três medidas', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    const { fixture } = await mount(203);
    fixture.destroy();
    expect(FakeObserver.last?.disconnected).toBe(true);
    names.forEach((name) => expect(read(name)).toBe(''));
  });
});
