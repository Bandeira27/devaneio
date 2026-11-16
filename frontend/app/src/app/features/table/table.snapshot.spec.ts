import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ApiClient } from '@core/api/api-client';
import { apiInterceptor } from '@core/api/api.interceptor';
import { TABLE_ID, campaignView, tableView } from '../../testing/fixtures';
import { TableSnapshot } from './table.snapshot';

function setup() {
  TestBed.configureTestingModule({
    providers: [provideHttpClient(withInterceptors([apiInterceptor])), provideHttpClientTesting()],
  });
  const http = TestBed.inject(HttpTestingController);
  const snapshot = new TableSnapshot(TestBed.inject(ApiClient), () => TABLE_ID);
  const reads = () => ({
    table: http.expectOne(`/tables/${TABLE_ID}`),
    campaign: http.expectOne(`/tables/${TABLE_ID}/campaign`),
  });
  return { http, snapshot, reads };
}

describe('TableSnapshot', () => {
  it('lê a mesa e a cena e guarda a revisão', async () => {
    const { snapshot, reads } = setup();
    expect(snapshot.revision()).toBe(0);
    const done = snapshot.refresh();
    const { table, campaign } = reads();
    table.flush(tableView({ revision: 5 }));
    campaign.flush(campaignView());
    await done;
    expect(snapshot.revision()).toBe(5);
    expect(snapshot.campaign()?.title).toBe('A Sombra do Vale');
  });

  it('um pedido durante uma leitura em voo vira uma leitura nova, depois do pedido', async () => {
    const { http, snapshot, reads } = setup();
    const first = snapshot.refresh();
    const second = snapshot.refresh(); // chega com a primeira em voo
    expect(second).toBe(first);
    const one = reads();
    one.table.flush(tableView({ revision: 5 }));
    one.campaign.flush(campaignView());
    await Promise.resolve();
    await Promise.resolve();
    const two = reads(); // a segunda leitura começou sozinha
    two.table.flush(tableView({ revision: 6 }));
    two.campaign.flush(campaignView());
    await first;
    expect(snapshot.revision()).toBe(6);
    http.verify();
  });

  it('depois de parar, não começa leitura nova', async () => {
    const { http, snapshot } = setup();
    snapshot.stop();
    await snapshot.refresh();
    http.expectNone(`/tables/${TABLE_ID}`);
  });

  it('uma falha de leitura não derruba quem chamou e deixa a foto como estava', async () => {
    const { snapshot, reads } = setup();
    const done = snapshot.refresh();
    const { table, campaign } = reads();
    table.flush({ error: { code: 'x', message: 'falhou' } }, { status: 500, statusText: 'x' });
    campaign.flush(campaignView());
    await expect(done).resolves.toBeUndefined();
    expect(snapshot.table()).toBeNull();
  });
});
