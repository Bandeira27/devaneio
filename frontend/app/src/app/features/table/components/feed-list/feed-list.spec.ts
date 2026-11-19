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

describe('FeedList', () => {
  let scrolled: ReturnType<typeof vi.fn>;
  let reduced = false;

  beforeEach(() => {
    reduced = false;
    scrolled = vi.fn();
    Element.prototype.scrollIntoView =
      scrolled as unknown as typeof Element.prototype.scrollIntoView;
    vi.stubGlobal('matchMedia', () => ({ matches: reduced }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
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

  it('a carga inicial entra sem animar', async () => {
    const { root } = await loaded();
    expect(root.querySelectorAll('.feed__event--new').length).toBe(0);
  });

  it('o item que aparece depois anima e a tela vai até ele, de forma suave', async () => {
    const { fixture, host, root } = await loaded();
    host.items.set([event(0), event(1)]);
    await fixture.whenStable();
    await Promise.resolve();
    expect(root.querySelectorAll('.feed__event--new').length).toBe(1);
    expect((scrolled.mock.contexts.at(-1) as HTMLElement).getAttribute('data-key')).toBe('e1');
    expect(scrolled).toHaveBeenLastCalledWith({ block: 'nearest', behavior: 'smooth' });
  });

  it('com movimento reduzido a rolagem é direta', async () => {
    const { fixture, host } = await loaded();
    reduced = true;
    host.items.set([event(0), event(1)]);
    await fixture.whenStable();
    await Promise.resolve();
    expect(scrolled).toHaveBeenLastCalledWith({ block: 'nearest', behavior: 'auto' });
  });

  it('um toque no feed não pula nada: não há o que pular', async () => {
    const { fixture, host, root } = await loaded();
    host.items.set([event(0), event(1)]);
    await fixture.whenStable();
    await Promise.resolve();
    scrolled.mockClear();
    (root.querySelector('dv-feed-list') as HTMLElement).click();
    await Promise.resolve();
    expect(scrolled).not.toHaveBeenCalled();
  });
});
