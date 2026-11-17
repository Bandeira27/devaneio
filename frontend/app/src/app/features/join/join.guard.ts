import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { SessionStore } from '@core/session/session-store';

/** Quem já entrou nesta mesa por este navegador vai direto a ela, sem ver o formulário de convite nem por um instante. */
export const notJoinedYet: CanActivateFn = (route) => {
  const tableId = route.paramMap.get('tableId') ?? '';
  return inject(SessionStore).get(tableId) === null
    ? true
    : inject(Router).createUrlTree(['/mesa', tableId]);
};
