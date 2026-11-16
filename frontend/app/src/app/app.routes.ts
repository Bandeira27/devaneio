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
        loadChildren: () => import('@features/home/home.routes').then((m) => m.HOME_ROUTES),
      },
      {
        path: 'entrar/:tableId/:invite',
        loadChildren: () => import('@features/join/join.routes').then((m) => m.JOIN_ROUTES),
      },
      {
        path: 'entrar/:tableId',
        loadChildren: () => import('@features/join/join.routes').then((m) => m.JOIN_ROUTES),
      },
      {
        path: 'mesa/:tableId/convite',
        loadChildren: () => import('@features/invite/invite.routes').then((m) => m.INVITE_ROUTES),
      },
      {
        path: 'mesa/:tableId/personagem',
        loadChildren: () =>
          import('@features/character/character.routes').then((m) => m.CHARACTER_ROUTES),
      },
      {
        path: 'mesa/:tableId',
        loadChildren: () => import('@features/table/table.routes').then((m) => m.TABLE_ROUTES),
      },
      { path: '**', redirectTo: '' },
    ],
  },
];
