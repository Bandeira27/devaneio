import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvButton } from '../button/button';
import { DvState } from './state';

const meta: Meta = { title: 'UI/Estado da tela' };
export default meta;

export const Carregando: StoryObj = story(
  [DvState],
  `<dv-state kind="loading">Abrindo a mesa…</dv-state>`,
);
export const Vazio: StoryObj = story(
  [DvState],
  `<dv-state>Nada aconteceu ainda. A história começa quando alguém agir.</dv-state>`,
);
export const Erro: StoryObj = story(
  [DvState, DvButton],
  `<dv-state kind="error">Não consegui abrir a mesa.<button dvStateAction dvButton type="button">Tentar de novo</button></dv-state>`,
);
export const Indisponivel: StoryObj = story(
  [DvState],
  `<dv-state kind="unavailable">O mestre de IA não está respondendo agora.</dv-state>`,
);
