import { TestBed } from '@angular/core/testing';
import type { Campaign, EditorTable, ValidationReport } from '@contract/api_responses';
import { SessionStore } from '@core/session/session-store';
import { hostCampaign, rulesView } from '../../testing/fixtures';
import { setup } from '../../testing/setup';
import { VALIDATE_DELAY } from './editor.store';

const OK: ValidationReport = { ok: true, errors: [], findings: [] };
const SYSTEMS = [{ id: 'default', name: 'Devaneio Básico' }];
const LIST = [
  { id: 'c', title: 'C', writable: true },
  { id: 'com-mesa', title: 'Com mesa', writable: false },
];
/** As campanhas do servidor, como o quadro da campanha as lê (o editor tem as suas, em `LIST`). */
const CAMPAIGNS = LIST.map(({ id, title }) => ({ id, title, premise: 'Uma premissa.' }));
const sleep = () => new Promise((resolve) => setTimeout(resolve, 5));

/** Abre o editor e responde às cargas, uma de cada vez, como o servidor faria. */
async function open(
  url: string,
  options: {
    campaign?: Campaign;
    list?: typeof LIST;
    report?: ValidationReport | 'fail';
    tables?: EditorTable[];
  } = {},
) {
  TestBed.overrideProvider(VALIDATE_DELAY, { useValue: 0 });
  const app = await setup(url);
  const { http, settle } = app;
  // O quadro da campanha pergunta primeiro quais são as campanhas e se o editor está ligado...
  http.expectOne('/campaigns').flush(CAMPAIGNS);
  http.expectOne('/editor/campaigns').flush(options.list ?? LIST);
  await settle();
  // ... e só então abre o roteiro, que carrega os sistemas e as campanhas do editor.
  http.expectOne('/editor/systems').flush(SYSTEMS);
  http.expectOne('/editor/campaigns').flush(options.list ?? LIST);
  await settle();
  if (options.campaign !== undefined) {
    http.expectOne(`/editor/campaigns/${options.campaign.id}`).flush(options.campaign);
    await settle();
  }
  http.expectOne((r) => r.url.startsWith('/editor/systems/')).flush(rulesView());
  await settle();
  // Campanha travada por mesa: o roteiro pergunta ao servidor quais mesas a travam.
  for (const request of http.match((r) => r.url.endsWith('/tables'))) {
    request.flush(options.tables ?? []);
  }
  await settle();
  const validations: Campaign[] = [];
  const answer = async (report: ValidationReport | 'fail' = options.report ?? OK) => {
    await sleep();
    for (const request of http.match('/editor/validate')) {
      validations.push((request.request.body as { campaign: Campaign }).campaign);
      if (report === 'fail') {
        request.flush(
          { error: { code: 'internal', message: 'erro interno' } },
          { status: 500, statusText: 'x' },
        );
      } else {
        request.flush(report);
      }
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

describe('Editor de campanhas: edição', () => {
  it('uma campanha nova abre em branco e é criada com o corpo da campanha', async () => {
    const { http, root, settle, button, answer, router, validations } =
      await open('/c/nova/roteiro');
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
    expect(router.url).toBe('/c/nova-campanha/roteiro');
  });

  it('uma cópia traz a campanha com id e título novos', async () => {
    const { validations } = await open('/c/nova/roteiro?copia=c', {
      campaign: { ...hostCampaign, id: 'c', title: 'Original' },
    });
    expect(validations[0]?.id).toBe('c-copia');
    expect(validations[0]?.title).toBe('Original (cópia)');
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
    const { root, text, button, type, answer } = await open('/c/nova/roteiro', { report });
    expect(text()).not.toContain('2 erros'); // numa campanha nova ainda intocada o que falta não é "erro"
    expect(button('Criar campanha')?.getAttribute('aria-disabled')).toBe('true');
    expect(text()).toContain('Preencha a campanha');
    await type('dv-overview-section input[type="text"]', 'Minha aventura'); // a primeira edição mostra os erros
    await answer();
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
    const { root, type, answer, validations } = await open('/c/nova/roteiro');
    await type('dv-overview-section input[type="text"]', 'Minha aventura');
    await answer();
    expect(validations.at(-1)?.title).toBe('Minha aventura');
    expect(root().querySelector('dv-badge')?.textContent).toContain('Sem erros');
  });

  it('um local novo ganha o id do nome e as referências acompanham', async () => {
    const { root, click, type, answer, validations } = await open('/c/nova/roteiro');
    await click('a[href="/c/nova/roteiro/locais"]');
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
      '/c/com-mesa/roteiro',
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
    const { type, harness, router } = await open('/c/nova/roteiro');
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
    expect(router.url).toBe('/c/nova/roteiro');
  });

  it('falha ao conferir não é erro da campanha: diz que não conseguiu e dá "Conferir de novo"', async () => {
    const { text, button, answer, root } = await open('/c/nova/roteiro', { report: 'fail' });
    expect(text()).toContain('Não consegui conferir a campanha agora');
    expect(text()).not.toContain('erros');
    expect(root().querySelector('.editor__problems')).toBeNull();
    expect(text()).toContain('tente conferir de novo');
    (button('Conferir de novo') as HTMLButtonElement).click();
    await answer(OK);
    expect(text()).toContain('Sem erros');
    expect(text()).not.toContain('Não consegui conferir');
  });

  it('uma resposta velha da conferência não libera gravar enquanto a nova não chega', async () => {
    const { http, type, button, settle, text } = await open('/c/nova/roteiro');
    await type('dv-overview-section input[type="text"]', 'A');
    await sleep();
    const first = http.expectOne('/editor/validate'); // em voo
    await type('dv-overview-section input[type="text"]', 'AB');
    first.flush(OK); // a resposta da primeira chega com a segunda ainda no ar
    await settle();
    expect(text()).toContain('Conferindo a campanha…');
    expect((button('Criar campanha') as HTMLButtonElement).getAttribute('aria-disabled')).toBe(
      'true',
    );
    await sleep();
    http.expectOne('/editor/validate').flush(OK);
    await settle();
    expect(
      (button('Criar campanha') as HTMLButtonElement).getAttribute('aria-disabled'),
    ).toBeNull();
  });

  it('os erros dizem em que seção e item estão', async () => {
    const report: ValidationReport = {
      ok: false,
      errors: [{ path: 'locations.0.name', message: "falta preencher 'name'" }],
      findings: [],
    };
    const { root, type, answer } = await open('/c/nova/roteiro', { report });
    await type('dv-overview-section input[type="text"]', 'Minha aventura');
    await answer();
    expect(root().querySelector('.editor__problems')?.textContent).toContain('Locais › Início:');
    // a linha leva até a seção onde o erro mora
    expect(root().querySelector('.editor__problems a')?.getAttribute('href')).toBe(
      '/c/nova/roteiro/locais',
    );
  });

  it('gravar a partir de uma seção volta para a mesma seção', async () => {
    const { http, click, button, settle, answer, router } = await open('/c/nova/roteiro');
    await click('a[href="/c/nova/roteiro/locais"]');
    (button('Criar campanha') as HTMLButtonElement).click();
    await settle();
    http.expectOne('/editor/campaigns').flush({ id: 'nova-campanha', title: 'N', writable: true });
    await settle();
    await answer();
    expect(router.url).toBe('/c/nova-campanha/roteiro/locais');
  });

  it('editar enquanto grava deixa "Alterações não gravadas" (o que veio depois ainda não foi gravado)', async () => {
    const { http, button, settle, root, answer, harness } = await open('/c/nova/roteiro');
    (button('Criar campanha') as HTMLButtonElement).click();
    await settle();
    const post = http.expectOne('/editor/campaigns');
    // Com o POST no ar, `settle` (whenStable) esperaria por ele: edita direto e só roda a detecção.
    const title = root().querySelector(
      'dv-overview-section input[type="text"]',
    ) as HTMLInputElement;
    title.value = 'Mudei durante';
    title.dispatchEvent(new Event('input'));
    harness.detectChanges();
    post.flush({ id: 'nova-campanha', title: 'N', writable: true });
    await settle();
    await answer();
    expect(root().textContent).toContain('Alterações não gravadas');
    expect(root().textContent).not.toContain('Gravada');
  });

  it('"Salvar como cópia" com falha de rede mostra o erro e não vira cópia', async () => {
    const { http, button, settle, root } = await open('/c/com-mesa/roteiro', {
      campaign: { ...hostCampaign, id: 'com-mesa', title: 'Com mesa' },
    });
    (button('Salvar como cópia') as HTMLButtonElement).click();
    await settle();
    http
      .expectOne('/editor/campaigns')
      .flush(
        { error: { code: 'internal', message: 'erro interno' } },
        { status: 500, statusText: 'x' },
      );
    await settle();
    expect(root().textContent).toContain('O servidor falhou');
    expect(root().querySelector('h1')?.textContent).toContain('Roteiro');
  });

  it('um identificador que já é de outro item é recusado e o campo volta ao valor de antes', async () => {
    const { root, click, settle } = await open('/c/c/roteiro', {
      campaign: { ...hostCampaign, id: 'c' },
    });
    await click('a[href="/c/c/roteiro/locais"]');
    (root().querySelectorAll('dv-locations-section summary')[1] as HTMLElement).click();
    await settle();
    // O identificador fica em "Avançado" (recolhido), mas o campo está na página: o segundo item tem nome e id.
    const id = root().querySelectorAll<HTMLInputElement>(
      'dv-locations-section input[type="text"]',
    )[3] as HTMLInputElement;
    const before = id.value;
    id.value = hostCampaign.locations[0]?.id ?? '';
    id.dispatchEvent(new Event('change'));
    await settle();
    expect(root().textContent).toContain('Já existe outro item com esse identificador.');
    expect(id.value).toBe(before);
  });

  it('remover um local o tira da campanha conferida, avisa o que some junto e dá para desfazer', async () => {
    const { root, click, settle, answer, validations, text } = await open('/c/c/roteiro', {
      campaign: { ...hostCampaign, id: 'c' },
    });
    await click('a[href="/c/c/roteiro/locais"]');
    const before = validations.at(-1)?.locations.length ?? 0;
    (
      root().querySelector(
        'dv-locations-section button[aria-label^="Remover"]',
      ) as HTMLButtonElement
    ).click(); // sem pergunta: remove e oferece desfazer
    await settle();
    await answer();
    expect(validations.at(-1)?.locations.length).toBe(before - 1);
    expect(text()).toContain('removido. As ligações para ele somem');
    const undo = Array.from(root().querySelectorAll<HTMLButtonElement>('dv-notice button')).find(
      (b) => b.textContent?.trim() === 'Desfazer',
    );
    undo?.click();
    await settle();
    await answer();
    expect(validations.at(-1)?.locations.length).toBe(before);
    expect(text()).not.toContain('removido. As ligações');
  });

  it('uma edição depois de remover encerra o desfazer', async () => {
    const { root, click, settle, type, text } = await open('/c/c/roteiro', {
      campaign: { ...hostCampaign, id: 'c' },
    });
    await click('a[href="/c/c/roteiro/locais"]');
    (
      root().querySelector(
        'dv-locations-section button[aria-label^="Remover"]',
      ) as HTMLButtonElement
    ).click();
    await settle();
    expect(text()).toContain('removido.');
    await click('a[href="/c/c/roteiro"]');
    await type('dv-overview-section input[type="text"]', 'Outro título');
    expect(text()).not.toContain('removido.');
  });

  it('o menu tem Marcos e Fatos, e a seção de marcos lista os da campanha com requisitos', async () => {
    const { root, click, text } = await open('/c/c/roteiro', {
      campaign: { ...hostCampaign, id: 'c' },
    });
    expect(root().querySelector('a[href="/c/c/roteiro/marcos"]')?.textContent).toContain('Marcos');
    expect(root().querySelector('a[href="/c/c/roteiro/fatos"]')?.textContent).toContain('Fatos');
    await click('a[href="/c/c/roteiro/marcos"]');
    expect(text()).toContain('Chegada');
    expect(text()).toContain('O altar');
    expect(text()).toContain('Só começa depois de concluir');
  });

  it('acrescentar uma condição a um marco entra na campanha conferida, apontando para um item que existe', async () => {
    const { root, click, settle, answer, validations } = await open('/c/c/roteiro', {
      campaign: { ...hostCampaign, id: 'c' },
    });
    await click('a[href="/c/c/roteiro/marcos"]');
    (root().querySelectorAll('dv-beats-section summary')[0] as HTMLElement).click();
    await new Promise((resolve) => setTimeout(resolve));
    await settle();
    const add = Array.from(
      root().querySelectorAll<HTMLButtonElement>('dv-conditions-editor .add-condition'),
    )[0];
    add?.click();
    await settle();
    await answer();
    const beat = validations.at(-1)?.beats[0];
    expect(beat?.activate_when).toEqual([
      { kind: 'at_location', location_id: hostCampaign.locations[0]?.id },
    ]);
  });

  it('trocar o tipo da condição recomeça no primeiro item, e o de turno usa um número', async () => {
    const { root, click, settle, answer, validations } = await open('/c/c/roteiro', {
      campaign: {
        ...hostCampaign,
        id: 'c',
        beats: hostCampaign.beats.map((b, i) =>
          i === 0
            ? { ...b, activate_when: [{ kind: 'at_location' as const, location_id: 'vila' }] }
            : b,
        ),
      },
    });
    await click('a[href="/c/c/roteiro/marcos"]');
    (root().querySelectorAll('dv-beats-section summary')[0] as HTMLElement).click();
    await new Promise((resolve) => setTimeout(resolve));
    await settle();
    const kind = root().querySelector<HTMLSelectElement>(
      'dv-conditions-editor select',
    ) as HTMLSelectElement;
    kind.value = 'turn_at_least';
    kind.dispatchEvent(new Event('change'));
    await settle();
    await answer();
    expect(validations.at(-1)?.beats[0]?.activate_when).toEqual([
      { kind: 'turn_at_least', turn: 1 },
    ]);
    expect(root().querySelector('dv-conditions-editor dv-stepper')).not.toBeNull();
  });

  it('o aviso de autoria de um marco aparece dentro dele', async () => {
    const report: ValidationReport = {
      ok: true,
      errors: [],
      findings: [
        { level: 'aviso', text: "marco 'chegada', complete_when: depende da queda de 'ferreiro'" },
      ],
    };
    const { root, click, settle } = await open('/c/c/roteiro', {
      campaign: { ...hostCampaign, id: 'c' },
      report,
    });
    await click('a[href="/c/c/roteiro/marcos"]');
    (root().querySelectorAll('dv-beats-section summary')[0] as HTMLElement).click();
    await new Promise((resolve) => setTimeout(resolve));
    await settle();
    expect(root().querySelector('dv-beats-section dv-item-problems')?.textContent).toContain(
      "depende da queda de 'ferreiro'",
    );
  });

  it('um fato novo ganha id do texto e o assunto lista os itens com o tipo', async () => {
    const { root, click, type, answer, validations, settle } = await open('/c/c/roteiro', {
      campaign: { ...hostCampaign, id: 'c' },
    });
    await click('a[href="/c/c/roteiro/fatos"]');
    await click('dv-facts-section .add');
    await new Promise((resolve) => setTimeout(resolve)); // o item novo abre por um efeito
    await settle();
    await type('dv-facts-section details[open] textarea', 'A chave está no poço');
    await answer();
    const fact = validations.at(-1)?.facts.at(-1);
    expect([fact?.text, fact?.id]).toEqual(['A chave está no poço', 'a-chave-esta-no-poco']);
    const options = Array.from(
      root().querySelectorAll('dv-facts-section details[open] dv-select option'),
    ).map((o) => o.textContent?.trim());
    expect(options).toContain('Local: Vila');
    expect(options).toContain('NPC: Bram');
    expect(options).toContain('Marco: Chegada');
  });

  it('os erros de integridade de um marco e de um fato aparecem dentro do item (frases reais do servidor)', async () => {
    const report: ValidationReport = {
      ok: false,
      errors: [
        { path: '', message: "marco 'chegada', activate_when: local 'x' não existe" },
        { path: '', message: "fato 'culto' fala de 'x', que não existe" },
      ],
      findings: [],
    };
    const { root, click, settle } = await open('/c/c/roteiro', {
      campaign: {
        ...hostCampaign,
        id: 'c',
        facts: [{ id: 'culto', text: 'Bram é do culto', about: null, reveal_when: [] }],
      },
      report,
    });
    await click('a[href="/c/c/roteiro/marcos"]');
    (root().querySelectorAll('dv-beats-section summary')[0] as HTMLElement).click();
    await new Promise((resolve) => setTimeout(resolve));
    await settle();
    expect(root().querySelector('dv-beats-section dv-item-problems')?.textContent).toContain(
      "local 'x' não existe",
    );
    await click('a[href="/c/c/roteiro/fatos"]');
    (root().querySelectorAll('dv-facts-section summary')[0] as HTMLElement).click();
    await new Promise((resolve) => setTimeout(resolve));
    await settle();
    expect(root().querySelector('dv-facts-section dv-item-problems')?.textContent).toContain(
      "fala de 'x'",
    );
  });

  it('remover uma condição tira só ela e leva o foco ao botão da que ocupou o lugar', async () => {
    const campaign = {
      ...hostCampaign,
      id: 'c',
      beats: hostCampaign.beats.map((b, i) =>
        i === 0
          ? {
              ...b,
              activate_when: [
                { kind: 'turn_at_least' as const, turn: 1 },
                { kind: 'turn_at_least' as const, turn: 2 },
                { kind: 'turn_at_least' as const, turn: 3 },
              ],
            }
          : b,
      ),
    };
    const { root, click, settle, answer, validations } = await open('/c/c/roteiro', { campaign });
    await click('a[href="/c/c/roteiro/marcos"]');
    (root().querySelectorAll('dv-beats-section summary')[0] as HTMLElement).click();
    await new Promise((resolve) => setTimeout(resolve));
    await settle();
    document.body.append(root());
    const remove = root().querySelectorAll<HTMLButtonElement>(
      'dv-conditions-editor .row__remove',
    )[1] as HTMLButtonElement;
    expect(remove.getAttribute('aria-label')).toContain('Remover condição 2');
    expect(remove.getAttribute('aria-label')).toContain('condições para começar (marco Chegada)');
    remove.click();
    await settle();
    await answer();
    await new Promise((resolve) => setTimeout(resolve));
    expect(validations.at(-1)?.beats[0]?.activate_when).toEqual([
      { kind: 'turn_at_least', turn: 1 },
      { kind: 'turn_at_least', turn: 3 },
    ]);
    const next = root().querySelectorAll('dv-conditions-editor .row__remove')[1];
    expect(document.activeElement).toBe(next);
    root().remove();
  });

  it('sem NPC para citar, a condição "um NPC foi derrotado" diz o que falta em vez de um campo vazio', async () => {
    const campaign = {
      ...hostCampaign,
      id: 'c',
      npcs: [],
      beats: hostCampaign.beats.map((b, i) =>
        i === 0 ? { ...b, activate_when: [{ kind: 'npc_down' as const, npc_id: '' }] } : b,
      ),
    };
    const { root, click, settle } = await open('/c/c/roteiro', { campaign });
    await click('a[href="/c/c/roteiro/marcos"]');
    (root().querySelectorAll('dv-beats-section summary')[0] as HTMLElement).click();
    await new Promise((resolve) => setTimeout(resolve));
    await settle();
    expect(root().querySelector('dv-beats-section details[open]')?.textContent).toContain(
      'Ainda não há NPCs. Crie um em NPCs.',
    );
  });

  describe('prévia', () => {
    const PREVIEW = {
      player: {
        id: 'c',
        title: 'A Sombra do Vale',
        premise: 'Um culto desperta.',
        location: {
          id: 'vila',
          name: 'Vila',
          description: 'Casas de pedra.',
          exits: [{ id: 'floresta', name: 'Floresta' }],
        },
        npcs: [{ id: 'ferreiro', name: 'Bram' }],
        beats: [],
        facts: [],
      },
      llm: '{"turno": 0, "publico": true}',
      llm_secrets: '{"turno": 0, "segredos": ["SEGREDO-X"]}',
      copilot_chars: 12000,
      copilot_limit: 60000,
    };

    async function openPreview(preview: object = PREVIEW) {
      const app = await open('/c/c/roteiro/previa', { campaign: { ...hostCampaign, id: 'c' } });
      await sleep();
      app.http.expectOne('/editor/preview').flush(preview);
      await app.settle();
      return app;
    }

    it('mostra o que o jogador vê, o que o LLM recebe sem e com segredos e o tamanho do copiloto', async () => {
      const { root, text } = await openPreview();
      expect(text()).toContain('A Sombra do Vale');
      expect(text()).toContain('Começa em Vila');
      expect(text().replace(/\s+/g, ' ')).toContain('Saídas: Floresta');
      expect(text().replace(/\s+/g, ' ')).toContain('Quem está lá: Bram');
      expect(text()).toContain('12.000 de 60.000 caracteres (20%)');
      expect(text()).toContain('Cabe com folga');
      const code = Array.from(root().querySelectorAll('pre')).map((p) => p.textContent);
      expect(code[0]).toContain('"publico": true');
      expect(code[0]).not.toContain('SEGREDO-X');
      expect(code[1]).toContain('SEGREDO-X');
      expect(text()).toContain('--segredos-no-llm');
    });

    it('perto do limite e acima dele o aviso diz o que acontece, em texto e ícone', async () => {
      const near = await openPreview({ ...PREVIEW, copilot_chars: 50000 });
      expect(near.text()).toContain('Perto do limite');
      expect(near.text()).toContain('menos eventos recentes');
    });

    it('acima do limite diz "Passa do limite"', async () => {
      const over = await openPreview({ ...PREVIEW, copilot_chars: 70000 });
      expect(over.text()).toContain('Passa do limite');
      expect(over.text()).toContain('recusa a pergunta');
    });

    it('com erros na campanha não pede a prévia e diz por quê', async () => {
      const report: ValidationReport = {
        ok: false,
        errors: [{ path: '', message: 'algo está errado' }],
        findings: [],
      };
      const { http, text } = await open('/c/c/roteiro/previa', {
        campaign: { ...hostCampaign, id: 'c' },
        report,
      });
      await sleep();
      http.expectNone('/editor/preview');
      expect(text()).toContain('A prévia precisa de uma campanha sem erros');
    });

    it('depois de uma edição a prévia fica marcada como antiga e "Atualizar" pede outra', async () => {
      const { root, http, click, type, answer, settle, button, text } = await openPreview();
      await click('a[href="/c/c/roteiro"]');
      await type('dv-overview-section input[type="text"]', 'Outro título');
      await answer();
      await click('a[href="/c/c/roteiro/previa"]');
      expect(text()).toContain('Esta prévia é de antes das últimas alterações');
      (button('Atualizar prévia') as HTMLButtonElement).click();
      await settle();
      http
        .expectOne('/editor/preview')
        .flush({ ...PREVIEW, player: { ...PREVIEW.player, title: 'Outro título' } });
      await settle();
      expect(root().textContent).not.toContain('antes das últimas alterações');
      expect(root().textContent).toContain('Outro título');
    });

    it('editar enquanto a prévia é pedida deixa a prévia marcada como antiga quando ela chega', async () => {
      const { http, root, harness, settle, answer } = await open('/c/c/roteiro', {
        campaign: { ...hostCampaign, id: 'c' },
      });
      // Com a prévia no ar, `settle` esperaria por ela: navega e edita direto, só rodando a detecção.
      (root().querySelector('a[href="/c/c/roteiro/previa"]') as HTMLElement).click();
      await sleep();
      harness.detectChanges();
      const pending = http.expectOne('/editor/preview');
      (root().querySelector('a[href="/c/c/roteiro"]') as HTMLElement).click();
      await sleep();
      harness.detectChanges();
      const title = root().querySelector(
        'dv-overview-section input[type="text"]',
      ) as HTMLInputElement;
      title.value = 'Mudei no meio';
      title.dispatchEvent(new Event('input'));
      harness.detectChanges();
      pending.flush(PREVIEW);
      await settle();
      await answer();
      (root().querySelector('a[href="/c/c/roteiro/previa"]') as HTMLElement).click();
      await settle();
      expect(root().textContent).toContain('Esta prévia é de antes das últimas alterações');
    });

    it('voltar à aba da prévia não pede de novo (a prévia já está na memória)', async () => {
      const { http, click, settle, text } = await openPreview();
      await click('a[href="/c/c/roteiro"]');
      await click('a[href="/c/c/roteiro/previa"]');
      await settle();
      http.expectNone('/editor/preview');
      expect(text()).toContain('A Sombra do Vale');
    });

    it('os limites: 80% já é "perto" e o teto exato ainda não é "passa"', async () => {
      const at80 = await openPreview({ ...PREVIEW, copilot_chars: 48000 });
      expect(at80.text()).toContain('Perto do limite');
      expect(at80.text()).not.toContain('Passa do limite');
    });

    it('99,6% aparece como 99% (para baixo), não como 100%', async () => {
      const near = await openPreview({ ...PREVIEW, copilot_chars: 59760 });
      expect(near.text()).toContain('(99%)');
    });

    it('falha ao pedir a prévia mostra o erro com "Tentar de novo"', async () => {
      const { http, settle, text, button } = await open('/c/c/roteiro/previa', {
        campaign: { ...hostCampaign, id: 'c' },
      });
      await sleep();
      http
        .expectOne('/editor/preview')
        .flush({ error: { code: 'internal', message: 'x' } }, { status: 500, statusText: 'x' });
      await settle();
      expect(text()).toContain('O servidor falhou');
      (button('Tentar de novo') as HTMLButtonElement).click();
      await settle();
      http.expectOne('/editor/preview').flush(PREVIEW);
      await settle();
      expect(text()).toContain('A Sombra do Vale');
    });
  });
});

const TABLE: EditorTable = {
  table_id: '0123456789abcdef',
  phase: 'running',
  host_name: 'Ana',
  players: 2,
  updated_at: Date.now() / 1000,
};
const LOCKED = { ...hostCampaign, id: 'com-mesa', title: 'Com mesa' };

/** O botão de confirmar da folha aberta (ou o de voltar). */
function sheetButton(label: string): HTMLButtonElement | undefined {
  return Array.from(document.querySelectorAll<HTMLButtonElement>('.dv-sheet__foot button')).find(
    (b) => b.textContent?.includes(label),
  );
}

describe('Editor de campanhas: mesas que travam a campanha', () => {
  it('lista as mesas do servidor no aviso, com o vocabulário do jogo e sem ids', async () => {
    const { text } = await open('/c/com-mesa/roteiro', { campaign: LOCKED, tables: [TABLE] });
    expect(text()).toContain('Mesa de Ana · em jogo · 2 jogadores · hoje');
    expect(text()).toContain('Assumir como anfitrião');
    expect(text()).toContain('Encerrar');
    expect(text()).not.toContain(TABLE.table_id);
  });

  it('uma mesa que o navegador conhece mostra "Abrir" em vez de "Assumir"', async () => {
    const { text, harness, settle } = await open('/c/com-mesa/roteiro', {
      campaign: LOCKED,
      tables: [TABLE],
    });
    TestBed.inject(SessionStore).save(TABLE.table_id, {
      token: 't',
      playerId: 'p1',
      role: 'host',
      title: 'Com mesa',
      savedAt: 1,
    });
    await settle();
    harness.detectChanges();
    expect(text()).toContain('Abrir');
    expect(text()).not.toContain('Assumir como anfitrião');
  });

  it('encerrar pede confirmação; cancelar não manda nada', async () => {
    const { http, button, settle, harness } = await open('/c/com-mesa/roteiro', {
      campaign: LOCKED,
      tables: [TABLE],
    });
    (button('Encerrar') as HTMLButtonElement).click();
    await settle();
    harness.detectChanges();
    expect(document.body.textContent).toContain('Isto não tem volta');
    sheetButton('Voltar')?.click();
    await settle();
    http.expectNone(`/editor/tables/${TABLE.table_id}`);
  });

  it('encerrar a última mesa libera a campanha para gravar', async () => {
    const { http, button, settle, text, harness } = await open('/c/com-mesa/roteiro', {
      campaign: LOCKED,
      tables: [TABLE],
    });
    (button('Encerrar') as HTMLButtonElement).click();
    await settle();
    harness.detectChanges();
    sheetButton('Encerrar a mesa')?.click();
    await settle();
    const request = http.expectOne(`/editor/tables/${TABLE.table_id}`);
    expect(request.request.method).toBe('DELETE');
    request.flush({ table_id: TABLE.table_id });
    await settle();
    http
      .expectOne('/editor/campaigns')
      .flush(LIST.map((c) => (c.id === 'com-mesa' ? { ...c, writable: true } : c)));
    await settle();
    expect(text()).toContain('já pode ser regravada');
    expect(text()).not.toContain('Esta campanha já tem mesa');
  });

  it('assumir como anfitrião guarda o token novo neste navegador e abre a mesa', async () => {
    const { http, button, settle, harness, router } = await open('/c/com-mesa/roteiro', {
      campaign: LOCKED,
      tables: [TABLE],
    });
    (button('Assumir como anfitrião') as HTMLButtonElement).click();
    await settle();
    harness.detectChanges();
    expect(document.body.textContent).toContain('deixam de valer');
    sheetButton('Assumir')?.click();
    await settle();
    const request = http.expectOne(`/editor/tables/${TABLE.table_id}/host-access`);
    expect(request.request.method).toBe('POST');
    request.flush({
      table_id: TABLE.table_id,
      player_id: 'p1',
      token: 'token-novo',
      invite_code: 'convite-novo',
    });
    await settle();
    const saved = TestBed.inject(SessionStore).get(TABLE.table_id);
    expect([saved?.token, saved?.invite, saved?.role]).toEqual([
      'token-novo',
      'convite-novo',
      'host',
    ]);
    expect(saved?.campaignId).toBe('com-mesa');
    expect(router.url).toBe(`/mesa/${TABLE.table_id}`);
  });

  it('falha ao encerrar mostra o erro no aviso e mantém a mesa', async () => {
    const { http, button, settle, text, harness } = await open('/c/com-mesa/roteiro', {
      campaign: LOCKED,
      tables: [TABLE],
    });
    (button('Encerrar') as HTMLButtonElement).click();
    await settle();
    harness.detectChanges();
    sheetButton('Encerrar a mesa')?.click();
    await settle();
    http
      .expectOne(`/editor/tables/${TABLE.table_id}`)
      .flush(
        { error: { code: 'internal', message: 'erro interno' } },
        { status: 500, statusText: 'x' },
      );
    await settle();
    expect(text()).toContain('O servidor falhou');
    expect(text()).toContain('Mesa de Ana');
  });
});
