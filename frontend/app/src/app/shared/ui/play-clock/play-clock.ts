import { ChangeDetectionStrategy, Component, computed, effect, input, signal } from '@angular/core';
import { clockText, currentSeconds, spokenTime } from '@shared/game/play-time';

const LABELS = { running: 'Rodando', paused: 'Pausada', ended: 'Encerrada' } as const;

/**
 * O tempo de jogo de uma partida: "Rodando 1:23:45". Enquanto roda, anda sozinho a cada segundo a partir do valor que o
 * servidor contou (`seconds`, lido em `receivedAt`); na pausa e no fim fica parado. O relógio visual é decorativo para o
 * leitor de tela, que recebe a frase em minutos ("1 hora e 23 minutos"), sem anunciar segundo a segundo. Na sala de
 * espera não há tempo: o componente não mostra nada.
 */
@Component({
  selector: 'dv-play-clock',
  templateUrl: './play-clock.html',
  styleUrl: './play-clock.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class.clock--idle]': "phase() !== 'running'" },
})
export class DvPlayClock {
  /** A fase da mesa. */
  readonly phase = input.required<'lobby' | 'running' | 'paused' | 'ended'>();
  /** Os segundos que o servidor contou na última leitura. */
  readonly seconds = input.required<number>();
  /** Quando essa leitura chegou (ms do relógio do navegador). */
  readonly receivedAt = input.required<number>();

  private readonly now = signal(Date.now());
  protected readonly label = computed(() => {
    const phase = this.phase();
    return phase === 'lobby' ? '' : LABELS[phase];
  });
  private readonly current = computed(() =>
    currentSeconds(
      {
        seconds: this.seconds(),
        running: this.phase() === 'running',
        receivedAt: this.receivedAt(),
      },
      this.now(),
    ),
  );
  protected readonly visual = computed(() => clockText(this.current()));
  protected readonly spoken = computed(() => spokenTime(this.current()));

  constructor() {
    effect((onCleanup) => {
      if (this.phase() !== 'running') {
        return;
      }
      this.now.set(Date.now());
      const timer = setInterval(() => this.now.set(Date.now()), 1000);
      onCleanup(() => clearInterval(timer));
    });
  }
}
