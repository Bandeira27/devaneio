import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter, withComponentInputBinding } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { routes } from '../app.routes';
import { apiInterceptor } from '../core/api/api.interceptor';
import { SESSION_STORAGE, SessionStore } from '../core/session/session-store';

export class MemoryStorage {
  readonly data = new Map<string, string>();
  getItem(key: string): string | null {
    return this.data.get(key) ?? null;
  }
  setItem(key: string, value: string): void {
    this.data.set(key, value);
  }
}

/** A app de verdade (rotas reais, interceptor) com HTTP simulado e armazenamento em memória. */
export async function setup(url: string) {
  TestBed.configureTestingModule({
    providers: [
      provideRouter(routes, withComponentInputBinding()),
      provideHttpClient(withInterceptors([apiInterceptor])),
      provideHttpClientTesting(),
      { provide: SESSION_STORAGE, useValue: new MemoryStorage() },
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
  return { harness, http, router, session, root, settle, type, submit, click };
}
