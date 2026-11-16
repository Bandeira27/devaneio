import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvField } from './field';
import { DvInput } from './input';

const meta: Meta = {
  title: 'UI/Campo',
};
export default meta;

export const Padrao: StoryObj = story(
  [DvField, DvInput],
  `<dv-field label="Seu nome"><input dvInput type="text" /></dv-field>`,
);

export const ComDica: StoryObj = story(
  [DvField, DvInput],
  `<dv-field label="Link do convite" hint="Cole o link que o anfitrião mandou."><input dvInput type="text" /></dv-field>`,
);

export const ComErro: StoryObj = story(
  [DvField, DvInput],
  `<dv-field label="Seu nome" error="Escreva o seu nome."><input dvInput type="text" /></dv-field>`,
);

export const Selecao: StoryObj = story(
  [DvField, DvInput],
  `<dv-field label="Campanha"><select dvInput><option>A Sombra do Vale</option><option>O Último Farol</option></select></dv-field>`,
);

export const AreaDeTexto: StoryObj = story(
  [DvField, DvInput],
  `<dv-field label="O que você diz ou faz" hint="O mestre responde e, se for o caso, resolve a ação por você."><textarea dvInput rows="3"></textarea></dv-field>`,
);

export const Desabilitado: StoryObj = story(
  [DvField, DvInput],
  `<dv-field label="Endereço"><input dvInput type="text" value="localhost:8765" disabled /></dv-field>`,
);
