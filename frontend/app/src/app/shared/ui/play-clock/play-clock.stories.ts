import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvPlayClock } from './play-clock';

const meta: Meta = { title: 'UI/Relógio de jogo' };
export default meta;

export const Fases: StoryObj = story(
  [DvPlayClock],
  `<div style="display:grid;gap:.5rem">
    <dv-play-clock phase="running" [seconds]="3723" [receivedAt]="0" />
    <dv-play-clock phase="paused" [seconds]="3723" [receivedAt]="0" />
    <dv-play-clock phase="ended" [seconds]="7500" [receivedAt]="0" />
  </div>`,
);
