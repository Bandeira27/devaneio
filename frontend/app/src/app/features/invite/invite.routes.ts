import { Routes } from '@angular/router';
import { hostWithInvite } from './invite.guard';
import { InvitePage } from './pages/invite-page/invite-page';

export const INVITE_ROUTES: Routes = [
  { path: '', component: InvitePage, canActivate: [hostWithInvite] },
];
