import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { apiInterceptor } from '../api/api.interceptor';
import { CampaignCatalog } from './campaign-catalog';

const A = { id: 'a', title: 'A', premise: 'x' };
const B = { id: 'b', title: 'B', premise: 'y' };

describe('CampaignCatalog', () => {
  function setup() {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    return {
      catalog: TestBed.inject(CampaignCatalog),
      http: TestBed.inject(HttpTestingController),
    };
  }
  const flushProbe = (http: HttpTestingController) =>
    http.match('/editor/campaigns').forEach((r) => r.flush([]));
  const tick = () => new Promise((resolve) => setTimeout(resolve));

  it('lê as campanhas e `ensure` não pergunta de novo', async () => {
    const { catalog, http } = setup();
    const loading = catalog.ensure();
    http.expectOne('/campaigns').flush([A]);
    flushProbe(http);
    await loading;
    expect(catalog.find('a')?.title).toBe('A');
    await catalog.ensure();
    http.expectNone('/campaigns');
  });

  it('uma leitura pedida durante outra vem depois dela: não reaproveita uma resposta anterior ao pedido', async () => {
    const { catalog, http } = setup();
    const first = catalog.load();
    const second = catalog.load(); // a campanha B acabou de ser gravada
    http.expectOne('/campaigns').flush([A]); // a primeira leitura, feita antes de gravar
    flushProbe(http);
    await first;
    await tick();
    http.expectOne('/campaigns').flush([A, B]); // a segunda, depois
    flushProbe(http);
    await second;
    expect(catalog.find('b')?.title).toBe('B');
    expect(catalog.busy()).toBe(false);
  });

  it('chamadas durante a espera dividem a mesma segunda leitura', async () => {
    const { catalog, http } = setup();
    const first = catalog.load();
    const second = catalog.load();
    const third = catalog.load();
    http.expectOne('/campaigns').flush([A]);
    flushProbe(http);
    await first;
    await tick();
    http.expectOne('/campaigns').flush([A, B]); // uma só
    flushProbe(http);
    await Promise.all([second, third]);
    http.expectNone('/campaigns');
  });
});
