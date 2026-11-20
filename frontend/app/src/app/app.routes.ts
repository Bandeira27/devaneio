import { Routes } from '@angular/router';
import { CampaignShell } from '@layout/campaign-shell/campaign-shell';
import { Shell } from '@layout/shell/shell';
import {
  loadCampaignRoutes,
  loadCharacterRoutes,
  loadEditorRoutes,
  loadHomeRoutes,
  loadInviteRoutes,
  loadJoinRoutes,
  loadNewTableRoutes,
  loadSettingsRoutes,
  loadTableRoutes,
} from './route-loaders';

/** A configuração do roteador que as rotas pedem: as páginas de uma campanha leem o `campaignId` da rota de fora. */
export const ROUTER_CONFIG = { paramsInheritanceStrategy: 'always' } as const;

// Cada feature entra aqui, carregada sob demanda. Os parâmetros da rota chegam como `input()` nas páginas.
export const routes: Routes = [
  {
    path: '',
    component: Shell,
    children: [
      {
        path: '',
        pathMatch: 'full',
        title: 'Início',
        loadChildren: loadHomeRoutes,
      },
      // Criar mesa é o primeiro passo do caminho do anfitrião: fica fora do quadro da campanha, como as outras telas do caminho.
      {
        path: 'c/:campaignId/nova-mesa',
        title: 'Criar uma mesa',
        loadChildren: loadNewTableRoutes,
      },
      {
        path: 'c/:campaignId',
        component: CampaignShell,
        children: [
          {
            path: 'roteiro',
            loadChildren: loadEditorRoutes,
          },
          {
            path: '',
            loadChildren: loadCampaignRoutes,
          },
        ],
      },
      // A configuração do LLM é da máquina do servidor (como o roteiro): só abre neste computador.
      {
        path: 'configuracao',
        title: 'Configuração',
        loadChildren: loadSettingsRoutes,
      },
      {
        path: 'entrar/:tableId/:invite',
        title: 'Entrar na mesa',
        loadChildren: loadJoinRoutes,
      },
      {
        path: 'entrar/:tableId',
        title: 'Entrar na mesa',
        loadChildren: loadJoinRoutes,
      },
      {
        path: 'mesa/:tableId/convite',
        title: 'Convidar',
        loadChildren: loadInviteRoutes,
      },
      {
        path: 'mesa/:tableId/personagem',
        title: 'Seu personagem',
        loadChildren: loadCharacterRoutes,
      },
      {
        path: 'mesa/:tableId',
        title: 'Mesa',
        loadChildren: loadTableRoutes,
      },
      // O editor agora é o "roteiro" da campanha: os endereços antigos levam para lá.
      { path: 'editor/:campaignId/:section', redirectTo: 'c/:campaignId/roteiro/:section' },
      { path: 'editor/:campaignId', redirectTo: 'c/:campaignId/roteiro' },
      { path: 'editor', redirectTo: '' },
      { path: '**', redirectTo: '' },
    ],
  },
];
