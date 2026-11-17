import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvSteps } from './steps';

const meta: Meta = { title: 'UI/Passos' };
export default meta;

export const NoPersonagem: StoryObj = story(
  [DvSteps],
  `<dv-steps [steps]="['Mesa', 'Personagem', 'Jogar']" [current]="1" />`,
);
export const NoComeco: StoryObj = story(
  [DvSteps],
  `<dv-steps [steps]="['Mesa', 'Personagem', 'Jogar']" [current]="0" />`,
);
