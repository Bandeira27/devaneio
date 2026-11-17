import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import {
  PreloadAllModules,
  RouteReuseStrategy,
  TitleStrategy,
  provideRouter,
  withComponentInputBinding,
  withHashLocation,
  withPreloading,
  withViewTransitions,
} from '@angular/router';
import { apiInterceptor } from '@core/api/api.interceptor';
import { PageTitle } from './layout/shell/page-title';
import { routes } from './app.routes';
import { ParamsAwareReuse } from './route-reuse';

/**
 * A configuração do app. O roteamento é por hash (`/#/mesa/...`): o servidor só entrega `index.html` em `/`,
 * sem fallback de SPA, e o código do convite fica no fragmento, que nunca chega ao servidor nem ao log.
 */
export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(
      routes,
      withHashLocation(),
      withComponentInputBinding(),
      // As telas são poucas e pequenas: baixa todas em segundo plano, e a troca de tela quase nunca espera o código.
      // Só baixa: nenhum módulo de feature pode chamar a rede ao ser carregado (a rede é de `ngOnInit` e das stores).
      withPreloading(PreloadAllModules),
      // Troca de tela: só a página "vira" (o cabeçalho tem nome próprio e fica parado); com movimento reduzido, ou sem quadros sendo desenhados (aba escondida), troca na hora.
      withViewTransitions({
        onViewTransitionCreated: ({ transition }) => {
          if (
            document.visibilityState !== 'visible' ||
            matchMedia('(prefers-reduced-motion: reduce)').matches
          ) {
            transition.skipTransition();
          }
        },
      }),
    ),
    { provide: TitleStrategy, useExisting: PageTitle },
    { provide: RouteReuseStrategy, useClass: ParamsAwareReuse },
    provideHttpClient(withFetch(), withInterceptors([apiInterceptor])),
  ],
};
