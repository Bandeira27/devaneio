import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvChoice } from './choice';

const meta: Meta = { title: 'UI/Escolha' };
export default meta;

export const Dificuldade: StoryObj = story(
  [DvChoice],
  `<dv-choice legend="Dificuldade" value="normal" [options]="[
    { value: 'facil', label: 'Fácil' },
    { value: 'normal', label: 'Normal', detail: 'O padrão' },
    { value: 'dificil', label: 'Difícil' }
  ]" />`,
);

export const Alvo: StoryObj = story(
  [DvChoice],
  `<dv-choice legend="Alvo" [options]="[
    { value: 'goblin', label: 'Goblin', detail: '5 de 8 pontos de vida · hostil' },
    { value: 'bram', label: 'Bram', detail: '10 de 10 pontos de vida' }
  ]" />`,
);
