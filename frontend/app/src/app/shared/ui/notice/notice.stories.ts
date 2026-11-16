import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvNotice } from './notice';

const meta: Meta = {
  title: 'UI/Aviso',
};
export default meta;

export const Informacao: StoryObj = story(
  [DvNotice],
  `<dv-notice>Você ainda não tem personagem nesta mesa.</dv-notice>`,
);

export const Erro: StoryObj = story(
  [DvNotice],
  `<dv-notice kind="error">Sem conexão com o servidor.</dv-notice>`,
);

export const Confirmacao: StoryObj = story(
  [DvNotice],
  `<dv-notice kind="ok">A partida terminou: vitória.</dv-notice>`,
);

export const Atencao: StoryObj = story(
  [DvNotice],
  `<dv-notice kind="warn">O mestre de IA não está respondendo.</dv-notice>`,
);

export const Dispensavel: StoryObj = story(
  [DvNotice],
  `<dv-notice dismissible>Você pode dispensar este aviso.</dv-notice>`,
);
