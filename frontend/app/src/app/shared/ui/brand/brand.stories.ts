import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvBrand } from './brand';

const meta: Meta = { title: 'UI/Marca' };
export default meta;

export const Cabecalho: StoryObj = story([DvBrand], `<dv-brand />`);
export const Abertura: StoryObj = story([DvBrand], `<dv-brand size="lg" />`);
