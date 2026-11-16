import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withHashLocation } from '@angular/router';
import { routes } from './app.routes';

// Roteamento por hash (`/#/mesa/...`): o servidor Python só entrega `index.html` em `/`, sem fallback de
// SPA, e o código do convite fica no fragmento, que nunca chega ao servidor nem ao log.
export const appConfig: ApplicationConfig = {
  providers: [provideBrowserGlobalErrorListeners(), provideRouter(routes, withHashLocation())],
};
