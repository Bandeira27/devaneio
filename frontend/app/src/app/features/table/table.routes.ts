import { Routes } from '@angular/router';
import { HostRedirect } from './pages/host-redirect/host-redirect';
import { TableFrame } from './pages/table-frame/table-frame';
import { TablePage } from './pages/table-page/table-page';

/** A mesa e a rota antiga do painel dividem o `TableStore` do quadro (`TableFrame`). */
export const TABLE_ROUTES: Routes = [
  {
    path: '',
    component: TableFrame,
    children: [
      { path: '', pathMatch: 'full', component: TablePage },
      { path: 'anfitriao', component: HostRedirect },
    ],
  },
];
