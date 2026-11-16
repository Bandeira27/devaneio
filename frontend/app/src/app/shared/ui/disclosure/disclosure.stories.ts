import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvDisclosure } from './disclosure';

const meta: Meta = { title: 'UI/Detalhe' };
export default meta;

export const Fechado: StoryObj = story(
  [DvDisclosure],
  `<dv-disclosure label="Como foi resolvido"><p>Mira testa Lutar contra Normal: 2d6 [3, 4], total 10.</p></dv-disclosure>`,
);

export const Aberto: StoryObj = story(
  [DvDisclosure],
  `<dv-disclosure label="Como foi resolvido" [open]="true"><p>Mira testa Lutar contra Normal: 2d6 [3, 4], total 10.</p></dv-disclosure>`,
);
