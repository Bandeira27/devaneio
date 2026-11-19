import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import {
  Router,
  provideRouter,
  withComponentInputBinding,
  withRouterConfig,
} from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { ROUTER_CONFIG, routes } from '../app.routes';
import { apiInterceptor } from '../core/api/api.interceptor';
import { SESSION_STORAGE, SessionStore } from '../core/session/session-store';
import { REVEAL_CLOCK, RevealClock } from '../features/table/table.reveal';

export class MemoryStorage {
  readonly data = new Map<string, string>();
  getItem(key: string): string | null {
    return this.data.get(key) ?? null;
  }
  setItem(key: string, value: string): void {
    this.data.set(key, value);
  }
}

/**
 * O relógio da fila da história, na mão do teste: nada aparece até `advance` correr o tempo, como na tela de verdade
 * (todo texto novo espera). Sem relógio de parede e sem esperas fixas.
 */
export class ManualRevealClock implements RevealClock {
  private time = 0;
  private readonly timers: { at: number; fn: () => void; live: boolean }[] = [];
  stepMs(): number {
    return 1000;
  }
  now(): number {
    return this.time;
  }
  setTimer(fn: () => void, ms: number): () => void {
    const timer = { at: this.time + ms, fn, live: true };
    this.timers.push(timer);
    return () => {
      timer.live = false;
    };
  }
  /** Corre `ms` de tempo, disparando em ordem o que vence. */
  advance(ms: number): void {
    const end = this.time + ms;
    for (;;) {
      const next = this.timers.filter((t) => t.live && t.at <= end).sort((a, b) => a.at - b.at)[0];
      if (next === undefined) {
        break;
      }
      this.time = next.at;
      next.live = false;
      next.fn();
    }
    this.time = end;
  }
}

/** A app de verdade (rotas reais, interceptor) com HTTP simulado e armazenamento em memória. */
export async function setup(url: string) {
  const clock = new ManualRevealClock();
  TestBed.configureTestingModule({
    providers: [
      provideRouter(routes, withComponentInputBinding(), withRouterConfig(ROUTER_CONFIG)),
      provideHttpClient(withInterceptors([apiInterceptor])),
      provideHttpClientTesting(),
      { provide: SESSION_STORAGE, useValue: new MemoryStorage() },
      { provide: REVEAL_CLOCK, useValue: clock },
    ],
  });
  const harness = await RouterTestingHarness.create();
  const http = TestBed.inject(HttpTestingController);
  const router = TestBed.inject(Router);
  const session = TestBed.inject(SessionStore);
  await harness.navigateByUrl(url);
  const root = (): HTMLElement => harness.fixture.nativeElement as HTMLElement;
  // As respostas HTTP resolvem promessas e depois mexem em signals: espera os dois e roda a detecção.
  const settle = async (): Promise<void> => {
    for (let round = 0; round < 3; round++) {
      await Promise.resolve();
      await harness.fixture.whenStable();
      harness.detectChanges();
    }
  };
  /** Deixa passar o tempo da fila (`seconds` de leitura): o que esperava a vez aparece. */
  const reveal = async (seconds = 60): Promise<void> => {
    clock.advance(seconds * 1000);
    await settle();
  };
  const type = async (selector: string, value: string): Promise<void> => {
    const input = root().querySelector(selector) as HTMLInputElement | HTMLSelectElement;
    input.value = value;
    input.dispatchEvent(new Event(input instanceof HTMLSelectElement ? 'change' : 'input'));
    await settle();
  };
  const submit = async (): Promise<void> => {
    (root().querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit', { cancelable: true }),
    );
    await settle();
  };
  const click = async (selector: string): Promise<void> => {
    (root().querySelector(selector) as HTMLElement).click();
    await settle();
  };
  return { harness, http, router, session, root, settle, reveal, type, submit, click };
}
