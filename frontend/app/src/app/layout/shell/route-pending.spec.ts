import { TestBed } from '@angular/core/testing';
import {
  NavigationCancel,
  NavigationEnd,
  NavigationError,
  NavigationSkipped,
  NavigationStart,
  Router,
} from '@angular/router';
import { Subject } from 'rxjs';
import { RoutePending, SHOW_AFTER_MS } from './route-pending';

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

  it('`busy` vale do começo ao fim de toda navegação, mesmo a rápida', () => {
    start();
    expect(pending.busy()).toBe(true);
    end();
    expect(pending.busy()).toBe(false);
  });

  it('navegação rápida nunca mostra a folha', () => {
    start();
    vi.advanceTimersByTime(SHOW_AFTER_MS - 10);
    end();
    vi.advanceTimersByTime(SHOW_AFTER_MS * 4);
    expect(pending.visible()).toBe(false);
  });

  it('navegação lenta mostra a folha depois do atraso e a tira no instante em que acaba', () => {
    start();
    vi.advanceTimersByTime(SHOW_AFTER_MS + 1);
    expect(pending.visible()).toBe(true);
    end(); // a tela pronta não espera a folha
    expect(pending.visible()).toBe(false);
    expect(pending.busy()).toBe(false);
  });

  it.each([
    ['cancelada', () => new NavigationCancel(1, '/x', 'não')],
    ['com erro', () => new NavigationError(1, '/x', new Error('falhou'))],
  ])('navegação %s também encerra a espera', (_nome, make) => {
    start();
    vi.advanceTimersByTime(SHOW_AFTER_MS + 10);
    expect(pending.visible()).toBe(true);
    events.next(make());
    expect(pending.visible()).toBe(false);
    expect(pending.busy()).toBe(false);
  });

  it('navegação ignorada (mesma URL) também encerra a espera', () => {
    start();
    events.next(new NavigationSkipped(1, '/x', 'igual', 0));
    expect(pending.busy()).toBe(false);
  });

  it('uma navegação em cima da outra, ainda sem folha, conta o atraso desde a última', () => {
    start();
    vi.advanceTimersByTime(SHOW_AFTER_MS - 10);
    start();
    vi.advanceTimersByTime(SHOW_AFTER_MS - 10);
    expect(pending.visible()).toBe(false);
    vi.advanceTimersByTime(20);
    expect(pending.visible()).toBe(true);
  });

  it('ao destruir, a folha pendente não aparece depois', () => {
    start();
    TestBed.resetTestingModule(); // destrói o serviço: o temporizador tem de ser limpo
    vi.advanceTimersByTime(SHOW_AFTER_MS * 2);
    expect(pending.visible()).toBe(false);
  });

  it('um redirecionamento (cancela e recomeça) conta o atraso de novo, sem deixar a folha presa', () => {
    start();
    vi.advanceTimersByTime(SHOW_AFTER_MS + 1);
    events.next(new NavigationCancel(1, '/x', 'redirecionado'));
    start();
    expect(pending.visible()).toBe(false);
    vi.advanceTimersByTime(SHOW_AFTER_MS + 1);
    expect(pending.visible()).toBe(true);
    end();
    expect(pending.visible()).toBe(false);
  });
});
