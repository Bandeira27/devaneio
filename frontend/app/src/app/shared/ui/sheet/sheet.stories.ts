import { Component, inject, type AfterViewInit } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvButton } from '../button/button';
import { Sheet } from './sheet';
import { DvSheetHead } from './sheet-head';

/** Conteúdo de exemplo da folha. */
@Component({
  selector: 'dv-demo-sheet',
  imports: [DvSheetHead],
  template: `
    <dv-sheet-head title="Ir para" />
    <p class="dv-note">Conteúdo da folha.</p>
  `,
})
class DemoSheet {}

/** Botão que abre a folha de exemplo. */
@Component({
  selector: 'dv-demo-opener',
  imports: [DvButton],
  template: `<button dvButton type="button" (click)="open()">Abrir a folha</button>`,
})
class DemoOpener {
  private readonly sheet = inject(Sheet);

  protected open(): void {
    void this.sheet.open(DemoSheet, { label: 'Ir para' });
  }
}

/** Abre a folha de exemplo assim que aparece: é o estado real da folha (foco, aria, posição). */
@Component({ selector: 'dv-demo-auto-open', template: '' })
class DemoAutoOpen implements AfterViewInit {
  private readonly sheet = inject(Sheet);

  ngAfterViewInit(): void {
    void this.sheet.open(DemoSheet, { label: 'Ir para' });
  }
}

const meta: Meta = { title: 'UI/Folha' };
export default meta;

export const Fechada: StoryObj = story([DemoOpener], '<dv-demo-opener />');

export const Aberta: StoryObj = story([DemoAutoOpen], '<dv-demo-auto-open />');
