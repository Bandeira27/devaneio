/*
 * Os carregadores das rotas do app, um por feature. Cada um é um `import()` dinâmico de propósito: é ele que faz o
 * Angular dividir o app em pedaços e baixar uma feature só quando a rota dela abre. Por isso não viram imports
 * estáticos no topo de `app.routes.ts`, que puxariam todas as features para o pacote principal. Ficam aqui, com nome,
 * para a tabela de rotas ler como uma lista de caminhos e não como uma sequência de `import(...).then(...)`.
 */
import type { Routes } from '@angular/router';

/** As rotas de uma feature, carregadas sob demanda. */
type RouteLoader = () => Promise<Routes>;

export const loadHomeRoutes: RouteLoader = () =>
  import('@features/home/home.routes').then((m) => m.HOME_ROUTES);

export const loadNewTableRoutes: RouteLoader = () =>
  import('@features/campaign/new-table.routes').then((m) => m.NEW_TABLE_ROUTES);

export const loadEditorRoutes: RouteLoader = () =>
  import('@features/editor/editor.routes').then((m) => m.EDITOR_ROUTES);

export const loadCampaignRoutes: RouteLoader = () =>
  import('@features/campaign/campaign.routes').then((m) => m.CAMPAIGN_ROUTES);

export const loadSettingsRoutes: RouteLoader = () =>
  import('@features/settings/settings.routes').then((m) => m.SETTINGS_ROUTES);

export const loadJoinRoutes: RouteLoader = () =>
  import('@features/join/join.routes').then((m) => m.JOIN_ROUTES);

export const loadInviteRoutes: RouteLoader = () =>
  import('@features/invite/invite.routes').then((m) => m.INVITE_ROUTES);

export const loadCharacterRoutes: RouteLoader = () =>
  import('@features/character/character.routes').then((m) => m.CHARACTER_ROUTES);

export const loadTableRoutes: RouteLoader = () =>
  import('@features/table/table.routes').then((m) => m.TABLE_ROUTES);
