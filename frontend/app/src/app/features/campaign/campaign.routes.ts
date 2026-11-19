import { Routes } from '@angular/router';
import { OverviewPage } from './pages/overview-page/overview-page';
import { NewTablePage } from './pages/new-table-page/new-table-page';
import { TablesPage } from './pages/tables-page/tables-page';

/** As páginas de jogar de uma campanha, dentro do quadro com a barra lateral (`layout/campaign-shell`). */
export const CAMPAIGN_ROUTES: Routes = [
  { path: '', pathMatch: 'full', title: 'Campanha', component: OverviewPage },
  { path: 'mesas/nova', title: 'Criar uma mesa', component: NewTablePage },
  { path: 'mesas', title: 'Mesas', component: TablesPage },
];
