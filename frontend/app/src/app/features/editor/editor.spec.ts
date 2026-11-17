import { TestBed } from '@angular/core/testing';
import type { Campaign, ValidationReport } from '@contract/api_responses';
import { hostCampaign, rulesView } from '../../testing/fixtures';
import { setup } from '../../testing/setup';
import { VALIDATE_DELAY } from './editor.store';

const OK: ValidationReport = { ok: true, errors: [], findings: [] };
const SYSTEMS = [{ id: 'default', name: 'Devaneio Básico' }];
const LIST = [
  { id: 'c', title: 'C', writable: true },
  { id: 'com-mesa', title: 'Com mesa', writable: false },
];
const sleep = () => new Promise((resolve) => setTimeout(resolve, 5));

/** Abre o editor e responde às cargas, uma de cada vez, como o servidor faria. */
async function open(
  url: string,
  options: { campaign?: Campaign; list?: typeof LIST; report?: ValidationReport } = {},
) {
  TestBed.overrideProvider(VALIDATE_DELAY, { useValue: 0 });
  const app = await setup(url);
  const { http, settle } = app;
  http.expectOne('/editor/systems').flush(SYSTEMS);
  http.expectOne('/editor/campaigns').flush(options.list ?? LIST);
  await settle();
  if (options.campaign !== undefined) {
    http.expectOne(`/editor/campaigns/${options.campaign.id}`).flush(options.campaign);
    await settle();
  }
  http.expectOne((r) => r.url.startsWith('/editor/systems/')).flush(rulesView());
  await settle();
  const validations: Campaign[] = [];
  const answer = async (report: ValidationReport = options.report ?? OK) => {
    await sleep();
    for (const request of http.match('/editor/validate')) {
      validations.push((request.request.body as { campaign: Campaign }).campaign);
      request.flush(report);
    }
    await settle();
  };
  await answer();
  const text = () => app.root().textContent ?? '';
  const button = (label: string) =>
    Array.from(app.root().querySelectorAll<HTMLButtonElement>('button')).find((b) =>
      b.textContent?.includes(label),
    );
  return { ...app, answer, validations, text, button };
}

describe('Editor de campanhas: lista', () => {
  it('mostra as campanhas, marca a que tem mesa e oferece editar, copiar e uma nova', async () => {
    const app = await setup('/editor');
    app.http.expectOne('/editor/campaigns').flush(LIST);
    await app.settle();
    expect(app.root().textContent).toContain('Com mesa');
    expect(app.root().textContent).toContain('Tem mesa: só se copia');
    const links = Array.from(app.root().querySelectorAll('a')).map((a) => a.getAttribute('href'));
    expect(links).toContain('/editor/nova');
    expect(links).toContain('/editor/c');
    expect(links).toContain('/editor/nova?copia=com-mesa');
    expect(app.root().querySelector('a[aria-label="Ver Com mesa"]')).not.toBeNull();
  });

  it('sem --editor no servidor (404) diz que o editor está desligado', async () => {
    const app = await setup('/editor');
    app.http
      .expectOne('/editor/campaigns')
      .flush({ error: { code: 'not_found', message: 'x' } }, { status: 404, statusText: 'x' });
    await app.settle();
    expect(app.root().textContent).toContain('O editor está desligado');
    expect(app.root().querySelector('a[href="/editor/nova"]')).toBeNull();
  });
});

describe('Editor de campanhas: edição', () => {
  it('uma campanha nova abre em branco e é criada com o corpo da campanha', async () => {
    const { http, root, settle, button, answer, router, validations } = await open('/editor/nova');
    expect(root().querySelector('h1')?.textContent).toContain('Nova campanha');
    expect(validations[0]?.id).toBe('nova-campanha');
    const create = button('Criar campanha') as HTMLButtonElement;
    expect(create.getAttribute('aria-disabled')).toBeNull();
    create.click();
    await settle();
    const request = http.expectOne('/editor/campaigns');
    expect(request.request.method).toBe('POST');
    expect((request.request.body as { campaign: Campaign }).campaign.id).toBe('nova-campanha');
    request.flush({ id: 'nova-campanha', title: 'Nova campanha', writable: true });
    await settle();
    await answer();
    expect(router.url).toBe('/editor/nova-campanha');
  });

  it('uma cópia traz a campanha com id e título novos', async () => {
    const { text, validations } = await open('/editor/nova?copia=c', {
      campaign: { ...hostCampaign, id: 'c', title: 'Original' },
    });
    expect(validations[0]?.id).toBe('c-copia');
    expect(validations[0]?.title).toBe('Original (cópia)');
    expect(text()).toContain('c-copia');
  });

  it('os erros do servidor aparecem na lista, no campo e bloqueiam gravar com o motivo', async () => {
    const report: ValidationReport = {
      ok: false,
      errors: [
        { path: 'title', message: "'title' precisa ser um texto" },
        { path: '', message: "local 'x' conecta a 'y', que não existe" },
      ],
      findings: [{ level: 'aviso', text: 'marco depende da queda de um NPC' }],
    };
    const { root, text, button } = await open('/editor/nova', { report });
    expect(text()).toContain('2 erros');
    expect(text()).toContain("local 'x' conecta a 'y', que não existe");
    expect(text()).toContain('Avisos de autoria');
    expect(root().querySelector('[role="alert"]')?.textContent).toContain(
      "'title' precisa ser um texto",
    );
    const create = button('Criar campanha') as HTMLButtonElement;
    expect(create.getAttribute('aria-disabled')).toBe('true');
    expect(text()).toContain('Corrija os 2 erros antes de salvar.');
    expect(root().querySelector(`#${create.getAttribute('aria-describedby')}`)).not.toBeNull();
  });

  it('editar o título confere de novo, e o novo texto vai no corpo', async () => {
    const { root, type, answer, validations } = await open('/editor/nova');
    await type('dv-overview-section input[type="text"]', 'Minha aventura');
    await answer();
    expect(validations.at(-1)?.title).toBe('Minha aventura');
    expect(root().querySelector('dv-badge')?.textContent).toContain('Sem erros');
  });

  it('um local novo ganha o id do nome e as referências acompanham', async () => {
    const { root, click, type, answer, validations } = await open('/editor/nova');
    await click('a[href="/editor/nova/locais"]');
    await click('dv-locations-section .add');
    const name = root().querySelectorAll<HTMLInputElement>(
      'dv-locations-section input[type="text"]',
    );
    expect(name.length).toBeGreaterThan(0);
    await type('dv-locations-section details[open] input[type="text"]', 'Vila Velha');
    await answer();
    const last = validations.at(-1)?.locations.at(-1);
    expect([last?.name, last?.id]).toEqual(['Vila Velha', 'vila-velha']);
  });

  it('campanha que já tem mesa mostra o aviso e bloqueia gravar; salvar como cópia a torna nova', async () => {
    const { text, button, root, settle, http, answer, validations } = await open(
      '/editor/com-mesa',
      {
        campaign: { ...hostCampaign, id: 'com-mesa', title: 'Com mesa' },
      },
    );
    expect(text()).toContain('já tem mesa');
    expect((button('Gravar') as HTMLButtonElement).getAttribute('aria-disabled')).toBe('true');
    (button('Salvar como cópia') as HTMLButtonElement).click();
    await settle();
    http.expectOne('/editor/campaigns').flush(LIST);
    await settle();
    await answer();
    expect(validations.at(-1)?.id).toBe('com-mesa-copia');
    expect(root().querySelector('h1')?.textContent).toContain('Nova campanha');
  });

  it('sair com alterações não gravadas pede confirmação, e "Voltar" fica onde está', async () => {
    const { type, harness, router } = await open('/editor/nova');
    await type('dv-overview-section input[type="text"]', 'Mudei');
    const leaving = router.navigateByUrl('/');
    // A navegação espera a resposta do guarda: `settle` (whenStable) esperaria junto, então só cedemos o turno.
    for (
      let tries = 0;
      tries < 50 && !document.body.textContent?.includes('Descartar alterações?');
      tries++
    ) {
      await sleep();
      harness.detectChanges();
    }
    expect(document.body.textContent).toContain('Descartar alterações?');
    const back = Array.from(
      document.querySelectorAll<HTMLButtonElement>('.dv-sheet__foot button'),
    ).find((b) => b.textContent?.includes('Voltar'));
    back?.click();
    expect(await leaving).toBe(false);
    expect(router.url).toBe('/editor/nova');
  });
});
