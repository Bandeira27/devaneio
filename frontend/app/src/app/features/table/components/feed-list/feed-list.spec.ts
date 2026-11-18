import { Component, signal, viewChild } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import type { FeedItem } from '@shared/game/feed';
import { FeedList } from './feed-list';

/** Põe a janela bem longe do fim da página; devolve o que desfaz. */
function installFarFromEnd(): () => void {
  const original = Object.getOwnPropertyDescriptor(document.documentElement, 'scrollHeight');
  Object.defineProperty(document.documentElement, 'scrollHeight', {
    configurable: true,
    value: 5000,
  });
  return () => {
    if (original) {
      Object.defineProperty(document.documentElement, 'scrollHeight', original);
    } else {
      Reflect.deleteProperty(document.documentElement, 'scrollHeight');
    }
  };
}

function event(index: number): FeedItem {
  return {
    type: 'event',
    key: `e${index}`,
    index,
    turn: 1,
    kind: 'check',
    narration: `prosa ${index}`,
    note: `nota ${index}`,
    seal: null,
    fade: 0,
  };
}

@Component({
  imports: [FeedList],
  template: `<dv-feed-list [items]="items()" [loaded]="loaded()" />`,
})
class Host {
  readonly items = signal<FeedItem[]>([event(0)]);
  readonly loaded = signal(false);
  readonly feed = viewChild.required(FeedList);
}

describe('FeedList: a fila dos itens novos', () => {
  async function render() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    const steps = () =>
      Array.from(root.querySelectorAll<HTMLElement>('.feed__event--new')).map((el) =>
        el.style.getPropertyValue('--step'),
      );
    return { fixture, host: fixture.componentInstance, root, steps };
  }

  it('a carga inicial entra sem fila e sem animar', async () => {
    const { fixture, host, root } = await render();
    host.loaded.set(true);
    await fixture.whenStable();
    expect(root.querySelectorAll('.feed__event--new').length).toBe(0);
  });

  it('os itens de um golpe entram um de cada vez, na ordem', async () => {
    const { fixture, host, steps } = await render();
    host.loaded.set(true);
    await fixture.whenStable();
    host.items.set([event(0), event(1), event(2), event(3)]);
    await fixture.whenStable();
    expect(steps()).toEqual(['0', '1', '2']);
  });

  it('um lote grande entra todo de uma vez', async () => {
    const { fixture, host, steps } = await render();
    host.loaded.set(true);
    await fixture.whenStable();
    host.items.set([0, 1, 2, 3, 4, 5, 6].map(event));
    await fixture.whenStable();
    expect(steps().every((step) => step === '0')).toBe(true);
  });

  it('um toque no feed pula a espera, e um lote novo volta à fila', async () => {
    const { fixture, host, root, steps } = await render();
    host.loaded.set(true);
    await fixture.whenStable();
    host.items.set([event(0), event(1), event(2)]);
    await fixture.whenStable();
    expect(steps()).toEqual(['0', '1']);
    (root.querySelector('dv-feed-list') as HTMLElement).click();
    await fixture.whenStable();
    expect(steps()).toEqual(['0', '0']);
    host.items.set([event(0), event(1), event(2), event(3)]);
    await fixture.whenStable();
    expect(steps()).toEqual(['0', '1', '0']); // o lote novo (um item) volta a esperar a sua vez; os antigos já tocaram
  });
});

describe('FeedList: seguir o fim depois da ação própria', () => {
  let restore: () => void;
  let scrolled: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    restore = installFarFromEnd();
    scrolled = vi.fn();
    Element.prototype.scrollIntoView =
      scrolled as unknown as typeof Element.prototype.scrollIntoView;
  });

  afterEach(() => {
    restore();
  });

  async function loaded() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    fixture.componentInstance.loaded.set(true);
    await fixture.whenStable();
    await Promise.resolve(); // o rolar do primeiro item roda em microtarefa
    scrolled.mockClear();
    return { fixture, host: fixture.componentInstance };
  }

  it('longe do fim, o que chega de outros não leva a tela ao fim', async () => {
    const { fixture, host } = await loaded();
    host.items.set([event(0), event(1)]);
    await fixture.whenStable();
    await Promise.resolve();
    expect(scrolled).not.toHaveBeenCalled();
  });

  it('depois de `follow`, o resultado que chega leva a tela ao fim mesmo longe dele', async () => {
    const { fixture, host } = await loaded();
    host.feed().follow();
    await Promise.resolve();
    scrolled.mockClear();
    host.items.set([event(0), event(1)]);
    await fixture.whenStable();
    await Promise.resolve();
    expect(scrolled).toHaveBeenCalled();
  });
});
