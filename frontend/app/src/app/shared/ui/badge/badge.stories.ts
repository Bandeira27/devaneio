import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvBadge } from './badge';

const meta: Meta = { title: 'UI/Selo' };
export default meta;

export const Neutro: StoryObj = story([DvBadge], `<dv-badge>você</dv-badge>`);
export const Ok: StoryObj = story([DvBadge], `<dv-badge tone="ok" icon="ok">Ao vivo</dv-badge>`);
export const Atencao: StoryObj = story(
  [DvBadge],
  `<dv-badge tone="warn" icon="warn">já agiu</dv-badge>`,
);
export const Informacao: StoryObj = story(
  [DvBadge],
  `<dv-badge tone="info" icon="info">novo</dv-badge>`,
);
export const Erro: StoryObj = story(
  [DvBadge],
  `<dv-badge tone="danger" icon="danger">fora de combate</dv-badge>`,
);
export const Pendente: StoryObj = story(
  [DvBadge],
  `<dv-badge tone="info" [pending]="true">Conectando…</dv-badge>`,
);
