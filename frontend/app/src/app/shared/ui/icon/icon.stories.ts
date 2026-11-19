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
    <dv-icon name="info" /><dv-icon name="danger" /><dv-icon name="close" /><dv-icon name="add" />
    <dv-icon name="book" /><dv-icon name="table" /><dv-icon name="map" /><dv-icon name="person" />
    <dv-icon name="flag" /><dv-icon name="scroll" /><dv-icon name="eye" /><dv-icon name="menu" />
    <dv-icon name="back" /><dv-icon name="mail" /><dv-icon name="panel" /><dv-icon name="save" /><dv-icon name="copy" />
    <dv-icon name="retry" /><dv-icon name="undo" /><dv-icon name="trash" /><dv-icon name="up" />
    <dv-icon name="down" /><dv-icon name="play" />
  </div>`,
);
