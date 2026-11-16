import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvPips } from './pips';

const meta: Meta = {
  title: 'UI/Pontos de vida',
};
export default meta;

export const Cheio: StoryObj = story([DvPips], `<dv-pips [value]="10" [max]="10" />`);

export const Ferido: StoryObj = story([DvPips], `<dv-pips [value]="4" [max]="10" />`);

export const ForaDeCombate: StoryObj = story([DvPips], `<dv-pips [value]="0" [max]="10" />`);
