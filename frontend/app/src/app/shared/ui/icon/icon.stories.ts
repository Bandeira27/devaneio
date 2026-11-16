import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvIcon } from './icon';

const meta: Meta = { title: 'UI/Ícones' };
export default meta;

export const Conjunto: StoryObj = story(
  [DvIcon],
  `<div style="display:flex;gap:1rem;flex-wrap:wrap">
    <dv-icon name="go" /><dv-icon name="check" /><dv-icon name="attack" /><dv-icon name="sheet" />
    <dv-icon name="say" /><dv-icon name="command" /><dv-icon name="ok" /><dv-icon name="warn" />
    <dv-icon name="info" /><dv-icon name="danger" /><dv-icon name="close" />
  </div>`,
);
