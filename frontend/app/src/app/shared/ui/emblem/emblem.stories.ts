import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvEmblem } from './emblem';

const meta: Meta = { title: 'UI/Emblema' };
export default meta;

export const Campanhas: StoryObj = story(
  [DvEmblem],
  `<div style="display:flex;gap:1rem;flex-wrap:wrap;align-items:center">
    <dv-emblem campaignId="sombra-do-vale" size="lg" />
    <dv-emblem campaignId="mar-de-cinzas" size="lg" />
    <dv-emblem campaignId="a-torre" size="lg" />
    <dv-emblem campaignId="sombra-do-vale" />
  </div>`,
);
