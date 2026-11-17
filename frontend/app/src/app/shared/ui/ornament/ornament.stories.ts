import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvOrnament } from './ornament';

const meta: Meta = { title: 'UI/Ornamento' };
export default meta;

export const Padrao: StoryObj = story([DvOrnament], `<dv-ornament />`);
