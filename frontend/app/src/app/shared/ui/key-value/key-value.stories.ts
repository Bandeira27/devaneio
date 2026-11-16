import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvKeyValue } from './key-value';

const meta: Meta = { title: 'UI/Rótulo e valor' };
export default meta;

export const Cena: StoryObj = story(
  [DvKeyValue],
  `<dv-key-value [items]="[{ label: 'Saídas', value: 'Floresta Cinzenta' }, { label: 'Aqui', value: 'Bram' }]" />`,
);
