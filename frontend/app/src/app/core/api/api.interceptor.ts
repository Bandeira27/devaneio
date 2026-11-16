import { HttpContextToken, HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { SessionStore } from '../session/session-store';
import { ApiFailure } from './api-failure';

/** A mesa de quem faz a chamada: o interceptor põe o token dela no `Authorization` (nunca em URL). */
export const TABLE = new HttpContextToken<string | null>(() => null);

export const apiInterceptor: HttpInterceptorFn = (request, next) => {
  const tableId = request.context.get(TABLE);
  const token = tableId === null ? null : inject(SessionStore).tokenOf(tableId);
  const authorized =
    token === null ? request : request.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
  return next(authorized).pipe(
    catchError((error: unknown) =>
      throwError(() => (error instanceof HttpErrorResponse ? ApiFailure.from(error) : error)),
    ),
  );
};
