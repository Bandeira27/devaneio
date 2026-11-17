import { TestBed } from '@angular/core/testing';
import {
  NavigationCancel,
  NavigationEnd,
  NavigationError,
  NavigationStart,
  Router,
} from '@angular/router';
import { Subject } from 'rxjs';
import { MIN_VISIBLE_MS, RoutePending, SHOW_AFTER_MS } from './route-pending';

describe('RoutePending', () => {
  let events: Subject<unknown>;
  let pending: RoutePending;

  beforeEach(() => {
    vi.useFakeTimers();
    events = new Subject();
    TestBed.configureTestingModule({
      providers: [RoutePending, { provide: Router, useValue: { events } }],
    });
    pending = TestBed.inject(RoutePending);
  });

  afterEach(() => vi.useRealTimers());

  const start = () => events.next(new NavigationStart(1, '/x'));
  const end = () => events.next(new NavigationEnd(1, '/x', '/x'));

  it('navegação rápida nunca mostra a folha', () => {
    start();
    vi.advanceTimersByTime(SHOW_AFTER_MS - 10);
    end();
    vi.advanceTimersByTime(SHOW_AFTER_MS * 4);
    expect(pending.visible()).toBe(false);
  });

  it('navegação lenta mostra a folha depois do atraso e a segura pelo tempo mínimo', () => {
    start();
    vi.advanceTimersByTime(SHOW_AFTER_MS + 1);
    expect(pending.visible()).toBe(true);
    end(); // acabou logo depois de aparecer: a folha não pisca
    vi.advanceTimersByTime(MIN_VISIBLE_MS - 50);
    expect(pending.visible()).toBe(true);
    vi.advanceTimersByTime(100);
    expect(pending.visible()).toBe(false);
  });

  it('se já ficou o tempo mínimo, some assim que a navegação acaba', () => {
    start();
    vi.advanceTimersByTime(SHOW_AFTER_MS + MIN_VISIBLE_MS + 50);
    end();
    vi.advanceTimersByTime(1);
    expect(pending.visible()).toBe(false);
  });

  it.each([
    ['cancelada', () => new NavigationCancel(1, '/x', 'não')],
    ['com erro', () => new NavigationError(1, '/x', new Error('falhou'))],
  ])('navegação %s também encerra a espera', (_nome, make) => {
    start();
    vi.advanceTimersByTime(SHOW_AFTER_MS + MIN_VISIBLE_MS + 10);
    expect(pending.visible()).toBe(true);
    events.next(make());
    vi.advanceTimersByTime(1);
    expect(pending.visible()).toBe(false);
  });

  it('uma navegação em cima da outra mantém a folha em vez de piscar', () => {
    start();
    vi.advanceTimersByTime(SHOW_AFTER_MS + 1);
    end();
    start(); // antes do tempo mínimo acabar
    vi.advanceTimersByTime(MIN_VISIBLE_MS * 2);
    expect(pending.visible()).toBe(true);
    end();
    vi.advanceTimersByTime(1);
    expect(pending.visible()).toBe(false);
  });
});
