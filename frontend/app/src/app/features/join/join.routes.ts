import { Routes } from '@angular/router';
import { notJoinedYet } from './join.guard';
import { JoinPage } from './pages/join-page/join-page';

export const JOIN_ROUTES: Routes = [{ path: '', component: JoinPage, canActivate: [notJoinedYet] }];
