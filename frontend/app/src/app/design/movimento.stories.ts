import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { DvButton } from '../shared/ui/button/button';
import { story } from '../testing/story';

/** Mostra cada duração de movimento dos tokens (docs/movimento.md) com a curva padrão, uma linha por duração. */
@Component({
  selector: 'dv-demo-motion',
  imports: [DvButton],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p class="dv-note">
      Com movimento reduzido no sistema, as durações caem para 1 ms e a distância de entrada
      (--dv-motion-distance) para 0.
    </p>
    <button dvButton="primary" type="button" (click)="toggle()">Reproduzir</button>
    @for (row of rows; track row.name) {
      <div class="row">
        <code>{{ row.name }}</code>
        <div class="track">
          <span class="dot" [class]="'dot ' + row.cls" [class.moved]="moved()"></span>
        </div>
      </div>
    }
  `,
  styles: `
    .row {
      display: grid;
      grid-template-columns: minmax(0, 12rem) 1fr;
      align-items: center;
      gap: var(--dv-space-3);
      margin-top: var(--dv-space-3);
    }
    .track {
      container-type: inline-size;
      border-bottom: var(--dv-border-width) dotted var(--dv-line);
      padding-block: var(--dv-space-2);
    }
    .dot {
      display: block;
      width: var(--dv-size-pip);
      height: var(--dv-size-pip);
      border-radius: var(--dv-radius-round);
      background: var(--dv-accent);
      transition-property: transform;
      transition-timing-function: var(--dv-ease-standard);
    }
    .moved {
      transform: translateX(calc(100cqw - var(--dv-size-pip)));
    }
    .instant {
      transition-duration: var(--dv-duration-instant);
    }
    .fast {
      transition-duration: var(--dv-duration-fast);
    }
    .base {
      transition-duration: var(--dv-duration-base);
    }
    .slow {
      transition-duration: var(--dv-duration-slow);
    }
    .narrative {
      transition-duration: var(--dv-duration-narrative);
    }
  `,
})
class DemoMotion {
  protected readonly moved = signal(false);
  protected readonly rows = [
    { name: '--dv-duration-instant', cls: 'instant' },
    { name: '--dv-duration-fast', cls: 'fast' },
    { name: '--dv-duration-base', cls: 'base' },
    { name: '--dv-duration-slow', cls: 'slow' },
    { name: '--dv-duration-narrative', cls: 'narrative' },
  ];

  protected toggle(): void {
    this.moved.update((value) => !value);
  }
}

const meta: Meta = { title: 'Design/Movimento' };
export default meta;

export const Duracoes: StoryObj = story([DemoMotion], '<dv-demo-motion />');
