import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import {
  ActivatedRouteSnapshot,
  PreloadAllModules,
  RouteReuseStrategy,
  TitleStrategy,
  provideRouter,
  withComponentInputBinding,
  withHashLocation,
  withPreloading,
  withRouterConfig,
  withViewTransitions,
} from '@angular/router';
import { apiInterceptor } from '@core/api/api.interceptor';
import { PageTitle } from './layout/shell/page-title';
import { ROUTER_CONFIG, routes } from './app.routes';
import { ParamsAwareReuse } from './route-reuse';

/** Os segmentos do endereço de uma rota, da raiz até ela. */
function segmentsOf(route: ActivatedRouteSnapshot): string[] {
  return route.pathFromRoot.flatMap((part) => part.url.map((segment) => segment.path));
}

/**
 * Trocar de seção dentro do mesmo roteiro (`/c/<id>/roteiro/...`) não é trocar de tela: a página não "vira" (o título, o
 * status e a barra de gravar ficam parados) e só o conteúdo da seção entra.
 */
function sameSection(from: ActivatedRouteSnapshot, to: ActivatedRouteSnapshot): boolean {
  const before = segmentsOf(from);
  const after = segmentsOf(to);
  return (
    before[0] === 'c' &&
    before[2] === 'roteiro' &&
    before.slice(0, 3).join('/') === after.slice(0, 3).join('/')
  );
}

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
      // As páginas de dentro de uma campanha leem o `campaignId` da rota de fora (`/c/:campaignId/...`).
      withRouterConfig(ROUTER_CONFIG),
      // As telas são poucas e pequenas: baixa todas em segundo plano, e a troca de tela quase nunca espera o código.
      // Só baixa: nenhum módulo de feature pode chamar a rede ao ser carregado (a rede é de `ngOnInit` e das stores).
      withPreloading(PreloadAllModules),
      // Troca de tela: só a página "vira" (o cabeçalho tem nome próprio e fica parado); com movimento reduzido, ou sem quadros sendo desenhados (aba escondida), troca na hora.
      withViewTransitions({
        onViewTransitionCreated: ({ transition, from, to }) => {
          if (
            document.visibilityState !== 'visible' ||
            matchMedia('(prefers-reduced-motion: reduce)').matches ||
            sameSection(from, to)
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
