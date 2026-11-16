import { Routes } from '@angular/router';
import { Shell } from '@layout/shell/shell';

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
        title: 'Convite',
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
      { path: '**', redirectTo: '' },
    ],
  },
];
