import { Routes } from '@angular/router';
import type { CanDeactivateFn } from '@angular/router';
import { EditorListPage } from './pages/list-page/list-page';
import { EditorPage } from './pages/edit-page/edit-page';
import { FactionsSection } from './sections/factions-section';
import { LocationsSection } from './sections/locations-section';
import { NpcsSection } from './sections/npcs-section';
import { OverviewSection } from './sections/overview-section';

/** Sair da edição com alterações não gravadas pede confirmação. */
const leave: CanDeactivateFn<EditorPage> = (page) => page.canLeave();

export const EDITOR_ROUTES: Routes = [
  { path: '', pathMatch: 'full', component: EditorListPage },
  {
    path: ':campaignId',
    component: EditorPage,
    canDeactivate: [leave],
    children: [
      { path: '', pathMatch: 'full', component: OverviewSection },
      { path: 'locais', component: LocationsSection },
      { path: 'npcs', component: NpcsSection },
      { path: 'faccoes', component: FactionsSection },
    ],
  },
];
