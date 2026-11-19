import { InjectionToken, computed, signal } from '@angular/core';
import { revealWeight } from '@shared/game/reveal';

/** Quantos passos o primeiro texto de uma ação espera antes de aparecer: o mestre "pensando" antes de falar. */
export const REVEAL_LEAD_STEPS = 1;
/** O passo quando o token do CSS não chega (nunca zero: a espera não tem como ser desligada). */
export const REVEAL_STEP_FALLBACK_MS = 1000;

/** O que a fila pede ao mundo: assim ela é testável sem DOM nem relógio de verdade. */
export interface RevealClock {
  /** O tempo, em ms, de um passo da fila. Sempre maior que zero. */
  stepMs(): number;
  now(): number;
  /** Agenda `fn` e devolve como cancelar. */
  setTimer(fn: () => void, ms: number): () => void;
}

/** O relógio do navegador: o passo vem do token `--dv-reveal-step`, que nem o movimento reduzido zera. */
export const REVEAL_CLOCK = new InjectionToken<RevealClock>('REVEAL_CLOCK', {
  providedIn: 'root',
  factory: () => ({
    stepMs: () => {
      // Resolve o token como uma duração de verdade: o navegador devolve `1s`, `1000ms`, o que o CSS disser.
      const probe = document.createElement('span');
      probe.style.transitionDuration = 'var(--dv-reveal-step)';
      document.body.appendChild(probe);
      const value = getComputedStyle(probe).transitionDuration;
      probe.remove();
      const ms = parseFloat(value) * (value.endsWith('ms') ? 1 : 1000);
      return Number.isFinite(ms) && ms > 0 ? ms : REVEAL_STEP_FALLBACK_MS;
    },
    now: () => performance.now(),
    setTimer: (fn, ms) => {
      const timer = setTimeout(fn, ms);
      return () => clearTimeout(timer);
    },
  }),
});

/**
 * A fila única da história: todo texto novo da mesa (narração, fala, resposta do dock) entra aqui e só aparece na sua
 * vez. O primeiro espera `REVEAL_LEAD_STEPS`; cada um segura o seguinte pelo tempo de ler (`revealWeight`); o que chega
 * com a fila andando espera ela acabar. Não há lote, movimento reduzido nem gesto que entre de uma vez.
 */
export class RevealQueue {
  private readonly pending = signal(0);
  /** Nada à espera de aparecer: o que a tela mostra já alcançou o que o servidor mandou. */
  readonly idle = computed(() => this.pending() === 0);
  private endsAt = 0;
  private readonly cancels = new Set<() => void>();

  constructor(private readonly clock: RevealClock) {}

  /** Põe um texto de `textLength` caracteres na fila; `reveal` roda quando chega a vez dele. */
  enqueue(textLength: number, reveal: () => void): void {
    const step = this.clock.stepMs();
    const now = this.clock.now();
    const start = this.endsAt > now ? this.endsAt : now + REVEAL_LEAD_STEPS * step;
    this.endsAt = start + revealWeight(textLength) * step;
    this.pending.update((count) => count + 1);
    const cancel = this.clock.setTimer(() => {
      this.cancels.delete(cancel);
      this.pending.update((count) => count - 1);
      reveal();
    }, start - now);
    this.cancels.add(cancel);
  }

  /** Cancela o que falta (a tela foi embora). */
  dispose(): void {
    this.cancels.forEach((cancel) => cancel());
    this.cancels.clear();
    this.pending.set(0);
  }
}
