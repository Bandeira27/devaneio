import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvSelect } from './select';

const meta: Meta = { title: 'UI/Escolha de item' };
export default meta;

const OPTIONS = `[{ value: '', label: '(nenhum)' }, { value: 'vila', label: 'Vila' }, { value: 'floresta', label: 'Floresta' }]`;

export const Padrao: StoryObj = story(
  [DvSelect],
  `<dv-select label="Local de partida" value="vila" [options]="${OPTIONS}" />`,
);
export const ComDica: StoryObj = story(
  [DvSelect],
  `<dv-select label="Facção" hint="Quem manda neste NPC." [options]="${OPTIONS}" />`,
);
export const ComErro: StoryObj = story(
  [DvSelect],
  `<dv-select label="Local" error="Esse local não existe." value="fantasma" [options]="${OPTIONS}" />`,
);
