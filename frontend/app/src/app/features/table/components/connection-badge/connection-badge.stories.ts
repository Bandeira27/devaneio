import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../../../../testing/story';
import { ConnectionBadge } from './connection-badge';

const meta: Meta = {
  title: 'Mesa/Conexão',
};
export default meta;

const byStatus = (status: string): StoryObj =>
  story([ConnectionBadge], `<dv-connection-badge status="${status}" />`);

export const Conectando = byStatus('connecting');
export const AoVivo = byStatus('live');
export const SemConexao = byStatus('offline');
export const SessaoVencida = byStatus('expired');
export const MesaSumida = byStatus('gone');
export const Falha = byStatus('failed');
