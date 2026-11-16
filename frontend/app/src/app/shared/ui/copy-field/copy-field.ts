import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { DvButton } from '../button/button';

let nextId = 0;

type CopyState = 'idle' | 'copied' | 'manual';

/**
 * Texto para copiar (o link do convite). A API de área de transferência só existe em contexto seguro, e a mesa
 * costuma rodar em HTTP na rede local: então cai para `execCommand`, e se nem isso funcionar o texto já fica
 * selecionado para o jogador copiar à mão.
 */
@Component({
  selector: 'dv-copy-field',
  imports: [DvButton],
  templateUrl: './copy-field.html',
  styleUrl: './copy-field.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DvCopyField {
  protected readonly inputId = `dv-copy-${nextId++}`;
  readonly label = input.required<string>();
  readonly text = input.required<string>();

  protected readonly state = signal<CopyState>('idle');
  private readonly field = viewChild.required<ElementRef<HTMLInputElement>>('field');
  private timer: ReturnType<typeof setTimeout> | undefined;

  private legacyCopy(): boolean {
    try {
      return document.execCommand('copy');
    } catch {
      return false;
    }
  }

  protected select(): void {
    this.field().nativeElement.select();
  }

  protected async copy(): Promise<void> {
    this.select();
    let copied: boolean;
    try {
      await navigator.clipboard.writeText(this.text());
      copied = true;
    } catch {
      copied = this.legacyCopy();
    }
    this.state.set(copied ? 'copied' : 'manual');
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.state.set('idle'), 3000);
  }
}
