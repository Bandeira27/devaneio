import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../testing/story';
import { DvButton } from './button';

const meta: Meta = {
  title: 'UI/Botão',
};
export default meta;

export const Discreto: StoryObj = story([DvButton], `<button dvButton type="button">Ir</button>`);

export const Primario: StoryObj = story(
  [DvButton],
  `<button dvButton="primary" type="button">Falar</button>`,
);

export const Desabilitado: StoryObj = story(
  [DvButton],
  `<button dvButton type="button" disabled>Ir</button>`,
);

export const Bloqueado: StoryObj = story(
  [DvButton],
  `<button dvButton type="button" dvBlocked aria-describedby="motivo">Ir</button>
   <p id="motivo" class="dv-note">Seu personagem já agiu neste turno. Espere os outros.</p>`,
);

export const EmEnvio: StoryObj = story(
  [DvButton],
  `<button dvButton="primary" type="button" dvLoading>Enviando</button>`,
);
