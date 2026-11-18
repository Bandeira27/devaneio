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
