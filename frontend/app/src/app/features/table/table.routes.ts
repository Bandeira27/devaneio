import { Routes } from '@angular/router';
import { HostPage } from './pages/host-page/host-page';
import { TablePage } from './pages/table-page/table-page';

export const TABLE_ROUTES: Routes = [
  { path: '', pathMatch: 'full', component: TablePage },
  { path: 'anfitriao', title: 'Painel do anfitrião', component: HostPage },
];
