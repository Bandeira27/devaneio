import { Routes } from '@angular/router';
import type { CanDeactivateFn } from '@angular/router';
import { EditorPage } from './pages/edit-page/edit-page';
import { BeatsSection } from './sections/beats-section';
import { FactionsSection } from './sections/factions-section';
import { FactsSection } from './sections/facts-section';
import { LocationsSection } from './sections/locations-section';
import { NpcsSection } from './sections/npcs-section';
import { OverviewSection } from './sections/overview-section';
import { PreviewSection } from './sections/preview-section';

/** Sair da edição com alterações não gravadas pede confirmação. */
const leave: CanDeactivateFn<EditorPage> = (page) => page.canLeave();

/**
 * O roteiro de uma campanha, dentro do quadro com a barra lateral (`layout/campaign-shell`): as seções são páginas filhas
 * e o menu delas é a própria barra. O id da campanha (ou `nova`) vem da rota de fora, `/c/:campaignId/roteiro`.
 */
export const EDITOR_ROUTES: Routes = [
  {
    path: '',
    title: 'Roteiro',
    component: EditorPage,
    canDeactivate: [leave],
    children: [
      { path: '', pathMatch: 'full', component: OverviewSection },
      { path: 'locais', component: LocationsSection },
      { path: 'npcs', component: NpcsSection },
      { path: 'faccoes', component: FactionsSection },
      { path: 'marcos', component: BeatsSection },
      { path: 'fatos', component: FactsSection },
      { path: 'previa', component: PreviewSection },
    ],
  },
];
