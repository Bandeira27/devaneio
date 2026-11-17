import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { SessionStore } from '@core/session/session-store';

/** Só o anfitrião guarda o código do convite: quem chega sem ele é levado ao personagem, sem ver a tela do convite. */
export const hostWithInvite: CanActivateFn = (route) => {
  const tableId = route.paramMap.get('tableId') ?? '';
  const entry = inject(SessionStore).get(tableId);
  return entry?.role === 'host' && entry.invite !== undefined
    ? true
    : inject(Router).createUrlTree(['/mesa', tableId, 'personagem']);
};
