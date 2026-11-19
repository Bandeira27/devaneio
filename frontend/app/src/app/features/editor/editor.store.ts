import { DestroyRef, Injectable, InjectionToken, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import type {
  Campaign,
  EditorCampaign,
  EditorTable,
  PreviewView,
  RulesView,
  SystemInfo,
  ValidationReport,
} from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { ApiFailure, messageOf } from '@core/api/api-failure';
import { CampaignCatalog } from '@core/catalog/campaign-catalog';
import { CreatedCampaign, NEW_CAMPAIGN } from '@core/catalog/created-campaign';
import { SessionStore } from '@core/session/session-store';
import { ServerTables } from '@core/tables/server-tables';
import {
  addBeat,
  addFact,
  addFaction,
  addLocation,
  addNpc,
  emptyCampaign,
  freeId,
  idsOf,
  moveAt,
  removeItem,
  renameId,
  replaceAt,
  type ItemKind,
} from '@shared/game/campaign-edit';
import { slugify, uniqueId } from '@shared/game/names';
import { ASSUME_HOST_CONFIRM, CLOSE_TABLE_CONFIRM } from '@shared/game/server-tables';
import type { LoadState } from '@shared/game/load-state';
import { ConfirmSheet } from '@shared/ui/confirm/confirm-sheet';
import { Sheet } from '@shared/ui/sheet/sheet';

/** De que seção do roteiro é cada parte da campanha (o resto, como título e premissa, é a visão geral). */
const SECTION_OF: Record<string, string[]> = {
  locations: ['locais'],
  npcs: ['npcs'],
  factions: ['faccoes'],
  beats: ['marcos'],
  facts: ['fatos'],
};

/** Quanto se espera (ms) depois da última edição para conferir a campanha no servidor. */
export const VALIDATE_DELAY = new InjectionToken<number>('VALIDATE_DELAY', {
  providedIn: 'root',
  factory: () => 500,
});
export { NEW_CAMPAIGN };

/** As listas de itens da campanha que o editor mexe. */
type ListName = 'locations' | 'npcs' | 'factions' | 'beats' | 'facts';

/** Um item de uma lista da campanha, pelo tipo e pelo id (os ids são únicos dentro do tipo). */
const key = (kind: ItemKind, id: string): string => `${kind}:${id}`;

/**
 * O estado do editor de uma campanha: o que está sendo editado, a conferência do servidor, e salvar. A campanha é um
 * valor que se troca inteiro a cada edição (as funções de `campaign-edit` são puras); o servidor é quem valida, e
 * cada edição agenda uma conferência depois de uma pausa. Respostas atrasadas de conferências antigas são ignoradas.
 */
@Injectable()
export class EditorStore {
  private readonly api = inject(ApiClient);
  private readonly catalog = inject(CampaignCatalog);
  private readonly created = inject(CreatedCampaign);
  private readonly router = inject(Router);
  private readonly sheet = inject(Sheet);
  private readonly serverTables = inject(ServerTables);
  private readonly session = inject(SessionStore);
  private readonly delay = inject(VALIDATE_DELAY);

  readonly state = signal<LoadState>('loading');
  readonly loadError = signal('');
  readonly campaign = signal<Campaign | null>(null);
  /** O id com que a campanha está gravada, ou `null` se é nova (ou uma cópia que ainda não foi gravada). */
  readonly savedId = signal<string | null>(null);
  /** A campanha pode ser regravada? Falso quando alguma mesa a usa. */
  readonly writable = signal(true);
  /** As mesas do servidor que travam a campanha (só enquanto ela não pode ser regravada). */
  readonly tables = signal<EditorTable[]>([]);
  /** O que deu errado ao encerrar uma mesa ou assumir o lugar de anfitrião. */
  readonly tablesError = signal('');
  readonly systems = signal<SystemInfo[]>([]);
  readonly rules = signal<RulesView | null>(null);
  readonly report = signal<ValidationReport | null>(null);
  readonly validating = signal(false);
  /** A última remoção, para o aviso com "Desfazer" (some na próxima edição). */
  readonly removed = signal<{
    message: string;
    before: Campaign;
    autoBefore: ReadonlySet<string>;
  } | null>(null);
  readonly saving = signal(false);
  readonly saveError = signal('');
  readonly justSaved = signal(false);
  /** A conferência não chegou ao servidor (rede, servidor fora): não é erro da campanha, e dá para tentar de novo. */
  readonly checkError = signal('');
  /** O editor não atende este pedido (servidor com `--sem-editor`, ou o app aberto de fora da máquina do servidor)? */
  readonly unavailable = signal(false);
  /** Um aviso curto para o autor (por exemplo, "agora é uma cópia"). */
  readonly info = signal('');
  /** A prévia do que cada um enxerga (jogador, LLM, copiloto), ou `null` até ser pedida. */
  readonly preview = signal<PreviewView | null>(null);
  readonly previewing = signal(false);
  readonly previewError = signal('');
  private readonly previewOf = signal('');
  private previewSequence = 0;
  /** A prévia é de antes das últimas alterações? */
  readonly previewStale = computed(
    () => this.preview() !== null && this.previewOf() !== JSON.stringify(this.campaign()),
  );

  /** Os itens cujo id ainda acompanha o nome (chave `tipo:id`); um sinal, porque a tela mostra a dica dele. */
  private readonly auto = signal<ReadonlySet<string>>(new Set());
  private readonly savedText = signal('');
  private timer: ReturnType<typeof setTimeout> | undefined;
  private sequence = 0;
  /** A navegação que acompanha a gravação (para o endereço da campanha nova) não pede confirmação de descarte. */
  private navigatingAfterSave = false;
  /** O id da campanha nova acompanha o título até o autor escrevê-lo à mão. */
  private readonly autoCampaignId = signal(false);

  readonly isNew = computed(() => this.savedId() === null);
  readonly dirty = computed(() => {
    const campaign = this.campaign();
    return campaign !== null && JSON.stringify(campaign) !== this.savedText();
  });
  /**
   * Uma campanha nova em branco, ainda sem nenhuma edição: o servidor já aponta o que falta, mas isso não é "erro" do
   * autor, que ainda nem começou. Os erros só aparecem depois da primeira edição.
   */
  readonly pristine = signal(false);
  readonly errors = computed(() => (this.pristine() ? [] : (this.report()?.errors ?? [])));
  readonly findings = computed(() => this.report()?.findings ?? []);
  /** Por que não dá para salvar agora (texto), ou `''` se dá. */
  readonly saveBlock = computed(() => {
    if (this.saving()) {
      return 'Gravando…';
    }
    if (!this.isNew() && !this.writable()) {
      return 'Esta campanha já tem mesa e não pode ser regravada: salve uma cópia.';
    }
    if (this.checkError() !== '') {
      return 'Não consegui conferir a campanha agora: tente conferir de novo.';
    }
    if (this.validating() || this.report() === null) {
      return 'Conferindo a campanha…';
    }
    if (this.pristine() && (this.report()?.errors.length ?? 0) > 0) {
      return 'Preencha a campanha para poder gravá-la.';
    }
    if (this.errors().length > 0) {
      return `Corrija ${this.errors().length === 1 ? 'o erro' : 'os ' + this.errors().length + ' erros'} antes de salvar.`;
    }
    if (!this.isNew() && !this.dirty()) {
      return this.justSaved() ? 'Gravada.' : 'Nada mudou desde a última gravação.';
    }
    return '';
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.timer));
  }

  /** Abre uma campanha da pasta, uma em branco (`nova`) ou uma cópia (`nova` com `copyOf`). */
  async load(campaignId: string, copyOf = ''): Promise<void> {
    this.state.set('loading');
    this.loadError.set('');
    try {
      const [systems, list] = await Promise.all([
        firstValueFrom(this.api.editorSystems()),
        firstValueFrom(this.api.editorCampaigns()),
      ]);
      this.systems.set(systems);
      if (campaignId === NEW_CAMPAIGN) {
        await this.openNew(copyOf, list);
      } else {
        const campaign = await firstValueFrom(this.api.editorCampaign(campaignId));
        this.start(campaign, campaignId, list.find((c) => c.id === campaignId)?.writable ?? true);
      }
      await this.loadRules();
      await this.loadTables();
      this.state.set('ready');
      this.scheduleValidation(0);
    } catch (error) {
      this.unavailable.set(
        error instanceof ApiFailure && error.status === 404 && campaignId === NEW_CAMPAIGN,
      );
      this.loadError.set(messageOf(error));
      this.state.set('failed');
    }
  }

  private async openNew(copyOf: string, list: EditorCampaign[]): Promise<void> {
    if (copyOf === '') {
      this.start(emptyCampaign('nova-campanha', 'Nova campanha'), null, true);
      this.autoCampaignId.set(true);
      this.pristine.set(true);
      return;
    }
    const source = await firstValueFrom(this.api.editorCampaign(copyOf));
    const id = uniqueId(
      `${source.id}-copia`,
      list.map((c) => c.id),
    );
    this.start({ ...source, id, title: copyTitle(source.title) }, null, true);
  }

  private start(campaign: Campaign, savedId: string | null, writable: boolean): void {
    this.campaign.set(campaign);
    this.savedId.set(savedId);
    this.writable.set(writable);
    this.report.set(null);
    this.checkError.set('');
    this.info.set('');
    this.preview.set(null);
    this.previewError.set('');
    this.previewSequence++; // uma prévia pedida para a campanha anterior não vale mais
    this.previewing.set(false);
    this.autoCampaignId.set(false);
    this.auto.set(new Set());
    this.savedText.set(JSON.stringify(campaign));
  }

  private async loadRules(): Promise<void> {
    const id = this.campaign()?.rules_id ?? '';
    try {
      this.rules.set(id === '' ? null : await firstValueFrom(this.api.editorSystem(id)));
    } catch (error) {
      if (!(error instanceof ApiFailure && error.status === 404)) {
        throw error;
      }
      this.rules.set(null); // sistema que não existe: o validador diz, e as armas ficam sem lista
    }
  }

  // --- edição ---------------------------------------------------------------------

  /** Troca a campanha por uma versão nova e agenda a conferência. */
  update(change: (campaign: Campaign) => Campaign): void {
    const current = this.campaign();
    if (current === null) {
      return;
    }
    const next = change(current);
    this.campaign.set(next);
    this.pristine.set(false);
    this.removed.set(null); // qualquer edição encerra o desfazer da remoção anterior (quem remove o põe de volta depois)
    this.justSaved.set(false);
    if (next.rules_id !== current.rules_id) {
      void this.loadRules().catch(() => this.rules.set(null));
    }
    this.scheduleValidation(this.delay);
  }

  /** Muda o título; numa campanha nova em branco, o identificador acompanha o título até ser escrito à mão. */
  setTitle(title: string): void {
    const auto = this.autoCampaignId();
    this.update((c) => ({ ...c, title, id: auto ? slugify(title, 'campanha') : c.id }));
  }

  /** O autor escreveu o identificador da campanha: ele deixa de acompanhar o título. */
  setCampaignId(id: string): void {
    this.autoCampaignId.set(false);
    this.update((c) => ({ ...c, id }));
  }

  /** Acrescenta um item novo ao fim da lista do tipo; o id dele acompanha o nome até o autor escrevê-lo à mão. */
  add(kind: ItemKind): void {
    const current = this.campaign();
    if (current === null) {
      return;
    }
    const next = {
      location: addLocation,
      npc: addNpc,
      faction: addFaction,
      beat: addBeat,
      fact: addFact,
    }[kind](current);
    const list = {
      location: next.locations,
      npc: next.npcs,
      faction: next.factions,
      beat: next.beats,
      fact: next.facts,
    }[kind];
    const created = list.at(-1);
    if (created !== undefined) {
      this.setAuto(key(kind, created.id), true);
    }
    this.update(() => next);
  }

  /**
   * Remove um item e guarda a campanha de antes para **desfazer** (em vez de perguntar antes): `message` diz o que foi
   * removido e o que some junto. O desfazer vale até a próxima edição; depois dela, o aviso some.
   */
  remove(kind: ItemKind, id: string, message: string): void {
    const before = this.campaign();
    const autoBefore = this.auto();
    this.setAuto(key(kind, id), false);
    this.update((c) => removeItem(c, kind, id));
    if (before !== null) {
      this.removed.set({ message, before, autoBefore });
    }
  }

  /** Volta a campanha ao que era antes da última remoção. */
  undoRemove(): void {
    const removed = this.removed();
    if (removed === null) {
      return;
    }
    this.update(() => removed.before);
    this.auto.set(removed.autoBefore); // o id volta a acompanhar o nome, como antes
  }

  /** Muda o nome de um item; enquanto o id dele ainda é o gerado, o id acompanha o nome (e as referências também). */
  rename(kind: ItemKind, id: string, name: string, apply: (c: Campaign) => Campaign): void {
    const current = this.campaign();
    if (current === null) {
      return;
    }
    let next = apply(current);
    if (this.auto().has(key(kind, id))) {
      const fresh = freeId(next, kind, name, id);
      if (fresh !== id) {
        next = renameId(next, kind, id, fresh);
        this.setAuto(key(kind, id), false);
        this.setAuto(key(kind, fresh), true);
      }
    }
    this.update(() => next);
  }

  /**
   * O autor escreveu o id à mão: ele deixa de acompanhar o nome e as referências seguem o id novo. Devolve a frase do
   * problema (e não muda nada) se o id está vazio ou já é de outro item do mesmo tipo.
   */
  setId(kind: ItemKind, id: string, value: string): string {
    const current = this.campaign();
    if (current === null || value === id) {
      return '';
    }
    if (value === '') {
      return 'O identificador não pode ficar vazio.';
    }
    if (idsOf(current, kind).includes(value)) {
      return 'Já existe outro item com esse identificador.';
    }
    this.setAuto(key(kind, id), false);
    this.update((c) => renameId(c, kind, id, value));
    return '';
  }

  /** O id acompanha o nome? (para a tela dizer que o id é automático.) */
  isAuto(kind: ItemKind, id: string): boolean {
    return this.auto().has(key(kind, id));
  }

  private setAuto(itemKey: string, on: boolean): void {
    this.auto.update((set) => {
      const next = new Set(set);
      if (on) {
        next.add(itemKey);
      } else {
        next.delete(itemKey);
      }
      return next;
    });
  }

  replaceIn<L extends ListName>(list: L, index: number, item: Campaign[L][number]): void {
    this.update((c) => ({ ...c, [list]: replaceAt(c[list] as unknown[], index, item) }));
  }

  moveIn(list: ListName, index: number, delta: -1 | 1): void {
    this.update((c) => ({ ...c, [list]: moveAt(c[list] as unknown[], index, delta) }));
  }

  // --- conferência ----------------------------------------------------------------

  private scheduleValidation(delay: number): void {
    clearTimeout(this.timer);
    this.sequence++; // qualquer resposta de uma conferência anterior deixa de valer já
    this.validating.set(true);
    this.timer = setTimeout(() => void this.validate(), delay);
  }

  private async validate(): Promise<void> {
    const campaign = this.campaign();
    if (campaign === null) {
      return;
    }
    const mine = this.sequence;
    try {
      const report = await firstValueFrom(this.api.editorValidate(campaign));
      if (mine === this.sequence) {
        this.report.set(report);
        this.checkError.set('');
      }
    } catch (error) {
      if (mine === this.sequence) {
        this.report.set(null);
        this.checkError.set(messageOf(error)); // não é erro da campanha: dá para conferir de novo
      }
    } finally {
      if (mine === this.sequence) {
        this.validating.set(false);
      }
    }
  }

  /**
   * O que o servidor disse de um marco ou fato: erros de integridade e avisos de autoria (que vêm em frases que começam
   * por `marco 'id'` ou `fato 'id'`), para aparecerem junto do item.
   */
  problemsOf(
    word: 'marco' | 'fato',
    id: string,
  ): { errors: string[]; findings: { level: 'erro' | 'aviso'; text: string }[] } {
    const start = `${word} '${id}'`;
    return {
      errors: this.errors()
        .filter((e) => e.path === '' && e.message.startsWith(start))
        .map((e) => e.message),
      findings: this.findings().filter((f) => f.text.startsWith(start)),
    };
  }

  /** Pede a prévia da campanha como está agora (o servidor recusa se ela tem erros). */
  async loadPreview(): Promise<void> {
    const campaign = this.campaign();
    if (campaign === null || this.previewing()) {
      return;
    }
    const mine = ++this.previewSequence;
    this.previewing.set(true);
    this.previewError.set('');
    try {
      const preview = await firstValueFrom(this.api.editorPreview(campaign));
      if (mine === this.previewSequence) {
        this.preview.set(preview);
        this.previewOf.set(JSON.stringify(campaign)); // a campanha enviada, não a de agora: editar no meio deixa a prévia antiga
      }
    } catch (error) {
      if (mine === this.previewSequence) {
        this.previewError.set(messageOf(error));
      }
    } finally {
      if (mine === this.previewSequence) {
        this.previewing.set(false);
      }
    }
  }

  /** Confere de novo, sem esperar (depois de uma falha de conexão). */
  recheck(): void {
    this.scheduleValidation(0);
  }

  /** Onde mora cada erro, em palavras (`Locais › Floresta`), para a lista dizer em que seção e item o autor deve olhar. */
  readonly errorLines = computed(() => {
    const campaign = this.campaign();
    return this.errors().map((e) => ({
      where: campaign === null ? '' : whereIs(campaign, e.path),
      /** A seção do roteiro onde o erro mora (o caminho depois de `roteiro`), para a linha levar até ela. */
      section: SECTION_OF[e.path.split('.')[0] ?? ''] ?? [],
      message: e.message,
    }));
  });

  /** As frases de erro de um campo (`locations.0.name`) ou de tudo dentro dele (`locations.0`). */
  errorAt(path: string): string {
    const found = this.errors().find((e) => e.path === path || e.path.startsWith(`${path}.`));
    return found?.message ?? '';
  }

  // --- gravar ---------------------------------------------------------------------

  /** As mesas que travam a campanha, ou nada se ela pode ser regravada. */
  async loadTables(): Promise<void> {
    const id = this.savedId();
    this.tables.set(
      id !== null && !this.writable() ? ((await this.serverTables.list(id)) ?? []) : [],
    );
  }

  /** O navegador já tem o acesso a esta mesa (dá para abri-la sem assumir)? */
  knowsTable(tableId: string): boolean {
    return this.session.get(tableId) !== null;
  }

  /** Encerra uma mesa (depois de confirmar) e libera a campanha se era a última que a travava. */
  async closeTable(tableId: string): Promise<void> {
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Encerrar a mesa',
      data: CLOSE_TABLE_CONFIRM,
    });
    if (ok !== true) {
      return;
    }
    this.tablesError.set('');
    try {
      await this.serverTables.close(tableId);
      const id = this.savedId();
      const list = await firstValueFrom(this.api.editorCampaigns());
      this.writable.set(list.find((c) => c.id === id)?.writable ?? true);
      await this.loadTables();
      this.info.set(
        this.writable() ? 'Mesa encerrada. A campanha já pode ser regravada.' : 'Mesa encerrada.',
      );
    } catch (error) {
      this.tablesError.set(messageOf(error));
    }
  }

  /** Assume o lugar de anfitrião de uma mesa (depois de confirmar) e vai para ela. */
  async assumeHost(tableId: string): Promise<void> {
    const campaign = this.campaign();
    const id = this.savedId();
    if (campaign === null || id === null) {
      return;
    }
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Assumir como anfitrião',
      data: ASSUME_HOST_CONFIRM,
    });
    if (ok !== true) {
      return;
    }
    this.tablesError.set('');
    try {
      await this.serverTables.assumeHost(tableId, { id, title: campaign.title });
      await this.router.navigate(['/mesa', tableId]);
    } catch (error) {
      this.tablesError.set(messageOf(error));
    }
  }

  /** Prepara a gravação como cópia: id novo, e a campanha passa a ser nova. */
  async startCopy(): Promise<boolean> {
    this.saveError.set('');
    try {
      const taken = (await firstValueFrom(this.api.editorCampaigns())).map((c) => c.id);
      this.savedId.set(null);
      this.writable.set(true);
      this.update((c) => ({
        ...c,
        id: uniqueId(`${c.id}-copia`, taken),
        title: copyTitle(c.title),
      }));
      this.info.set('Agora é uma cópia: escolha o título e grave.');
      return true;
    } catch (error) {
      this.saveError.set(messageOf(error));
      return false;
    }
  }

  async save(): Promise<boolean> {
    const campaign = this.campaign();
    if (campaign === null || this.saveBlock() !== '') {
      return false;
    }
    this.saving.set(true);
    this.saveError.set('');
    try {
      const savedId = this.savedId();
      const result =
        savedId === null
          ? await firstValueFrom(this.api.editorCreate(campaign))
          : await firstValueFrom(this.api.editorUpdate(savedId, campaign));
      this.savedId.set(result.id);
      this.writable.set(result.writable);
      void this.catalog.load(); // o catálogo de campanhas (título, novidade) acompanha o que foi gravado
      this.savedText.set(JSON.stringify(campaign));
      this.justSaved.set(this.campaign() === campaign); // se o autor editou durante a gravação, ainda há o que gravar
      if (savedId === null) {
        const section = this.router.url.split('?')[0]?.split('/').slice(4) ?? []; // o que vem depois de /c/<id>/roteiro
        this.navigatingAfterSave = true;
        this.created.announce(result.id); // a tela segue a mesma: só o endereço troca `nova` pelo id
        try {
          await this.router.navigate(['/c', result.id, 'roteiro', ...section], {
            replaceUrl: true,
          });
        } finally {
          this.created.clear();
          this.navigatingAfterSave = false;
        }
      }
      return true;
    } catch (error) {
      this.saveError.set(messageOf(error));
      return false;
    } finally {
      this.saving.set(false);
    }
  }

  /** Pode sair da tela? Com alterações não gravadas, pergunta antes de descartar. */
  async canLeave(): Promise<boolean> {
    if (!this.dirty() || this.navigatingAfterSave) {
      return true;
    }
    const ok = await this.sheet.open<boolean>(ConfirmSheet, {
      label: 'Descartar alterações',
      data: {
        title: 'Descartar alterações?',
        text: 'A campanha tem alterações que não foram gravadas. Se sair agora, elas se perdem.',
        action: 'Descartar',
      },
    });
    return ok === true;
  }
}

/** O título de uma cópia, sem repetir o "(cópia)" ao copiar uma cópia. */
function copyTitle(title: string): string {
  return title.endsWith('(cópia)') ? title : `${title} (cópia)`;
}

const SECTION_LABEL = {
  locations: 'Locais',
  npcs: 'NPCs',
  factions: 'Facções',
  beats: 'Marcos',
  facts: 'Fatos',
} as const;

/** O lugar de um erro: `Locais › Floresta` para `locations.1.name`, `Visão geral` para os campos da campanha, ou `''`. */
function whereIs(campaign: Campaign, path: string): string {
  const [head, index] = path.split('.');
  if (head === undefined || head === '') {
    return '';
  }
  if (!(head in SECTION_LABEL)) {
    return 'Visão geral';
  }
  const list = campaign[head as keyof typeof SECTION_LABEL] as {
    name?: string;
    title?: string;
    text?: string;
    id: string;
  }[];
  const item = list[Number(index)];
  const label = SECTION_LABEL[head as keyof typeof SECTION_LABEL];
  return item === undefined
    ? label
    : `${label} › ${item.name || item.title || shorten(item.text) || item.id}`;
}

function shorten(text: string | undefined): string | undefined {
  return text === undefined ? undefined : text.length > 30 ? `${text.slice(0, 30)}…` : text;
}
