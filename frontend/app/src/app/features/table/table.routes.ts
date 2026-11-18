import { Routes } from '@angular/router';
import { HostPage } from './pages/host-page/host-page';
import { TableFrame } from './pages/table-frame/table-frame';
import { TablePage } from './pages/table-page/table-page';

/** A mesa e o painel do anfitrião dividem o `TableStore` do quadro (`TableFrame`). */
export const TABLE_ROUTES: Routes = [
  {
    path: '',
    component: TableFrame,
    children: [
      { path: '', pathMatch: 'full', component: TablePage },
      { path: 'anfitriao', title: 'Painel do anfitrião', component: HostPage },
    ],
  },
];
