import { Routes } from '@angular/router';
import { Shell } from '@layout/shell/shell';

// Cada feature entra aqui como rota filha, carregada sob demanda (`loadChildren`).
export const routes: Routes = [{ path: '', component: Shell, children: [] }];
