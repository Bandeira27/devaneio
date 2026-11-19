import { Routes } from '@angular/router';
import { CampaignShell } from '@layout/campaign-shell/campaign-shell';
import { Shell } from '@layout/shell/shell';

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
        loadChildren: () => import('@features/home/home.routes').then((m) => m.HOME_ROUTES),
      },
      // Criar mesa é o primeiro passo do caminho do anfitrião: fica fora do quadro da campanha, como as outras telas do caminho.
      {
        path: 'c/:campaignId/nova-mesa',
        title: 'Criar uma mesa',
        loadChildren: () =>
          import('@features/campaign/new-table.routes').then((m) => m.NEW_TABLE_ROUTES),
      },
      {
        path: 'c/:campaignId',
        component: CampaignShell,
        children: [
          {
            path: 'roteiro',
            loadChildren: () =>
              import('@features/editor/editor.routes').then((m) => m.EDITOR_ROUTES),
          },
          {
            path: '',
            loadChildren: () =>
              import('@features/campaign/campaign.routes').then((m) => m.CAMPAIGN_ROUTES),
          },
        ],
      },
      // A configuração do LLM é da máquina do servidor (como o roteiro): só abre neste computador.
      {
        path: 'configuracao',
        title: 'Configuração',
        loadChildren: () =>
          import('@features/settings/settings.routes').then((m) => m.SETTINGS_ROUTES),
      },
      {
        path: 'entrar/:tableId/:invite',
        title: 'Entrar na mesa',
        loadChildren: () => import('@features/join/join.routes').then((m) => m.JOIN_ROUTES),
      },
      {
        path: 'entrar/:tableId',
        title: 'Entrar na mesa',
        loadChildren: () => import('@features/join/join.routes').then((m) => m.JOIN_ROUTES),
      },
      {
        path: 'mesa/:tableId/convite',
        title: 'Convidar',
        loadChildren: () => import('@features/invite/invite.routes').then((m) => m.INVITE_ROUTES),
      },
      {
        path: 'mesa/:tableId/personagem',
        title: 'Seu personagem',
        loadChildren: () =>
          import('@features/character/character.routes').then((m) => m.CHARACTER_ROUTES),
      },
      {
        path: 'mesa/:tableId',
        title: 'Mesa',
        loadChildren: () => import('@features/table/table.routes').then((m) => m.TABLE_ROUTES),
      },
      // O editor agora é o "roteiro" da campanha: os endereços antigos levam para lá.
      { path: 'editor/:campaignId/:section', redirectTo: 'c/:campaignId/roteiro/:section' },
      { path: 'editor/:campaignId', redirectTo: 'c/:campaignId/roteiro' },
      { path: 'editor', redirectTo: '' },
      { path: '**', redirectTo: '' },
    ],
  },
];
