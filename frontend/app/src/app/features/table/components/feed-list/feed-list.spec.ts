import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import type { FeedItem } from '@shared/game/feed';
import { FeedList } from './feed-list';

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
    expect(steps()).toEqual(['1', '2', '3']);
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
    expect(steps()).toEqual(['1', '2']);
    (root.querySelector('dv-feed-list') as HTMLElement).click();
    await fixture.whenStable();
    expect(steps()).toEqual(['0', '0']);
    host.items.set([event(0), event(1), event(2), event(3)]);
    await fixture.whenStable();
    expect(steps()).toEqual(['1', '2', '1']); // o lote novo (um item) volta a esperar a sua vez; os antigos já tocaram
  });
});

describe('FeedList: acompanhar a fila', () => {
  let scrolled: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    scrolled = vi.fn();
    Element.prototype.scrollIntoView =
      scrolled as unknown as typeof Element.prototype.scrollIntoView;
  });

  afterEach(() => {
    vi.useRealTimers();
    Reflect.deleteProperty(Element.prototype, 'scrollIntoView');
  });

  async function loaded() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    fixture.componentInstance.loaded.set(true);
    await fixture.whenStable();
    await Promise.resolve();
    scrolled.mockClear();
    return { fixture, host: fixture.componentInstance, root: fixture.nativeElement as HTMLElement };
  }

  it('o que chega leva a tela até o item novo, mesmo de quem está no topo', async () => {
    const { fixture, host } = await loaded();
    host.items.set([event(0), event(1)]);
    await fixture.whenStable();
    vi.runAllTimers();
    expect(scrolled).toHaveBeenCalled();
    const element = scrolled.mock.contexts.at(-1) as HTMLElement;
    expect(element.getAttribute('data-key')).toBe('e1');
  });

  it('cada item da fila recebe a tela quando começa a aparecer, na ordem', async () => {
    const { fixture, host } = await loaded();
    host.items.set([event(0), event(1), event(2)]);
    await fixture.whenStable();
    vi.runAllTimers();
    const keys = scrolled.mock.contexts.map((el) => (el as HTMLElement).getAttribute('data-key'));
    expect(keys).toEqual(['e1', 'e2']);
  });

  it('um toque pula a espera e leva a tela ao fim', async () => {
    const { fixture, host, root } = await loaded();
    host.items.set([event(0), event(1), event(2)]);
    await fixture.whenStable();
    scrolled.mockClear();
    (root.querySelector('dv-feed-list') as HTMLElement).click();
    await Promise.resolve();
    vi.runAllTimers();
    expect(scrolled).toHaveBeenCalledWith({ block: 'end' });
    expect(scrolled.mock.contexts.some((el) => (el as HTMLElement).getAttribute('data-key'))).toBe(
      false,
    ); // nada mais é agendado
  });
});
