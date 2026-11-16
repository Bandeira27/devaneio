import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { provideRouter, withComponentInputBinding, withHashLocation } from '@angular/router';
import { apiInterceptor } from '@core/api/api.interceptor';
import { routes } from './app.routes';

/**
 * A configuração do app. O roteamento é por hash (`/#/mesa/...`): o servidor só entrega `index.html` em `/`,
 * sem fallback de SPA, e o código do convite fica no fragmento, que nunca chega ao servidor nem ao log.
 */
export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withHashLocation(), withComponentInputBinding()),
    provideHttpClient(withFetch(), withInterceptors([apiInterceptor])),
  ],
};
