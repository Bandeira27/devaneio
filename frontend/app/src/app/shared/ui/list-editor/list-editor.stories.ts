import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvListEditor } from './list-editor';

const meta: Meta = { title: 'UI/Lista editável' };
export default meta;

const NAME = `(item) => item`;

export const ComItens: StoryObj = story(
  [DvListEditor],
  `<dv-list-editor noun="local" [items]="['Vila de Pedra Alta', 'Floresta Cinzenta']" [nameOf]="${NAME}">
    <ng-template let-item><p class="dv-note">Aqui vai o formulário de {{ item }}.</p></ng-template>
  </dv-list-editor>`,
);
export const Vazia: StoryObj = story(
  [DvListEditor],
  `<dv-list-editor noun="NPC" empty="Nenhum NPC ainda." [items]="[]" [nameOf]="${NAME}">
    <ng-template let-item><p>{{ item }}</p></ng-template>
  </dv-list-editor>`,
);
