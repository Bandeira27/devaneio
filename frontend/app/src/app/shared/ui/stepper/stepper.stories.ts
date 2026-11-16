import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvStepper } from './stepper';

const meta: Meta = {
  title: 'UI/Atributo',
};
export default meta;

export const NoMeio: StoryObj = story(
  [DvStepper],
  `<dv-stepper label="Força" hint="Combate corpo a corpo." [min]="1" [max]="5" [value]="3" />`,
);

export const NoLimite: StoryObj = story(
  [DvStepper],
  `<dv-stepper label="Agilidade" hint="Rapidez e pontaria." [min]="1" [max]="5" [value]="5" />`,
);
