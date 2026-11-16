import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvCopyField } from './copy-field';

const meta: Meta = {
  title: 'UI/Campo de cópia',
};
export default meta;

export const Convite: StoryObj = story(
  [DvCopyField],
  `<dv-copy-field label="Link do convite" text="http://192.168.0.5:8765/#/entrar/0123456789abcdef/Ab-_9xYz1234ABcd" />`,
);
