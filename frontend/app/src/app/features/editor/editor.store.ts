import { DestroyRef, Injectable, InjectionToken, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import type {
  Campaign,
  EditorCampaign,
  RulesView,
  SystemInfo,
  ValidationReport,
} from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { messageOf } from '@core/api/api-failure';
import {
  addFaction,
  addLocation,
  addNpc,
  emptyCampaign,
  freeId,
  moveAt,
  removeItem,
  renameId,
  replaceAt,
  type ItemKind,
} from '@shared/game/campaign-edit';
import type { LoadState } from '@shared/game/load-state';
import { ConfirmSheet } from '@shared/ui/confirm/confirm-sheet';
import { Sheet } from '@shared/ui/sheet/sheet';

/** Quanto se espera (ms) depois da última edição para conferir a campanha no servidor. */
export const VALIDATE_DELAY = new InjectionToken<number>('VALIDATE_DELAY', {
  providedIn: 'root',
  factory: () => 500,
});
/** O id da rota de uma campanha que ainda não foi gravada. */
export const NEW_CAMPAIGN = 'nova';

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
  private readonly router = inject(Router);
  private readonly sheet = inject(Sheet);
  private readonly delay = inject(VALIDATE_DELAY);

  readonly state = signal<LoadState>('loading');
  readonly loadError = signal('');
  readonly campaign = signal<Campaign | null>(null);
  /** O id com que a campanha está gravada, ou `null` se é nova (ou uma cópia que ainda não foi gravada). */
  readonly savedId = signal<string | null>(null);
  /** A campanha pode ser regravada? Falso quando alguma mesa a usa. */
  readonly writable = signal(true);
  readonly systems = signal<SystemInfo[]>([]);
  readonly rules = signal<RulesView | null>(null);
  readonly report = signal<ValidationReport | null>(null);
  readonly validating = signal(false);
  readonly saving = signal(false);
  readonly saveError = signal('');
  readonly justSaved = signal(false);

  private readonly auto = new Set<string>();
  private timer: ReturnType<typeof setTimeout> | undefined;
  private sequence = 0;

  readonly isNew = computed(() => this.savedId() === null);
  readonly dirty = computed(() => {
    const campaign = this.campaign();
    return campaign !== null && JSON.stringify(campaign) !== this.savedText();
  });
  private readonly savedText = signal('');
  readonly errors = computed(() => this.report()?.errors ?? []);
  readonly findings = computed(() => this.report()?.findings ?? []);
  /** Por que não dá para salvar agora (texto), ou `''` se dá. */
  readonly saveBlock = computed(() => {
    if (this.saving()) {
      return 'Gravando…';
    }
    if (!this.isNew() && !this.writable()) {
      return 'Esta campanha já tem mesa e não pode ser regravada: salve uma cópia.';
    }
    if (this.validating() || this.report() === null) {
      return 'Conferindo a campanha…';
    }
    if (this.errors().length > 0) {
      return `Corrija ${this.errors().length === 1 ? 'o erro' : 'os ' + this.errors().length + ' erros'} antes de salvar.`;
    }
    if (!this.isNew() && !this.dirty()) {
      return 'Nada mudou desde a última gravação.';
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
      this.state.set('ready');
      this.scheduleValidation(0);
    } catch (error) {
      this.loadError.set(messageOf(error));
      this.state.set('failed');
    }
  }

  private async openNew(copyOf: string, list: EditorCampaign[]): Promise<void> {
    if (copyOf === '') {
      this.start(emptyCampaign('nova-campanha', 'Nova campanha'), null, true);
      return;
    }
    const source = await firstValueFrom(this.api.editorCampaign(copyOf));
    const taken = list.map((c) => c.id);
    const id = freeIdIn(`${source.id}-copia`, taken);
    this.start({ ...source, id, title: `${source.title} (cópia)` }, null, true);
  }

  private start(campaign: Campaign, savedId: string | null, writable: boolean): void {
    this.campaign.set(campaign);
    this.savedId.set(savedId);
    this.writable.set(writable);
    this.report.set(null);
    this.auto.clear();
    this.markSaved(JSON.stringify(campaign));
  }

  private markSaved(text: string): void {
    this.savedText.set(text);
  }

  private async loadRules(): Promise<void> {
    const id = this.campaign()?.rules_id ?? '';
    try {
      this.rules.set(id === '' ? null : await firstValueFrom(this.api.editorSystem(id)));
    } catch {
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
    this.justSaved.set(false);
    if (next.rules_id !== current.rules_id) {
      void this.loadRules();
    }
    this.scheduleValidation(this.delay);
  }

  /** Acrescenta um item novo ao fim da lista do tipo; o id dele acompanha o nome até o autor escrevê-lo à mão. */
  add(kind: Exclude<ItemKind, 'beat'>): void {
    const current = this.campaign();
    if (current === null) {
      return;
    }
    const next = { location: addLocation, npc: addNpc, faction: addFaction }[kind](current);
    const list = { location: next.locations, npc: next.npcs, faction: next.factions }[kind];
    const created = list.at(-1);
    if (created !== undefined) {
      this.auto.add(key(kind, created.id));
    }
    this.update(() => next);
  }

  remove(kind: ItemKind, id: string): void {
    this.auto.delete(key(kind, id));
    this.update((c) => removeItem(c, kind, id));
  }

  /** Muda o nome de um item; enquanto o id dele ainda é o gerado, o id acompanha o nome (e as referências também). */
  rename(kind: ItemKind, id: string, name: string, apply: (c: Campaign) => Campaign): void {
    this.update((c) => {
      const next = apply(c);
      if (!this.auto.has(key(kind, id))) {
        return next;
      }
      const fresh = freeId(next, kind, name, id);
      if (fresh === id) {
        return next;
      }
      this.auto.delete(key(kind, id));
      this.auto.add(key(kind, fresh));
      return renameId(next, kind, id, fresh);
    });
  }

  /** O autor escreveu o id à mão: ele deixa de acompanhar o nome e as referências seguem o id novo. */
  setId(kind: ItemKind, id: string, value: string): void {
    this.auto.delete(key(kind, id));
    this.update((c) => (value === '' || value === id ? c : renameId(c, kind, id, value)));
  }

  /** O id acompanha o nome? (para a tela dizer que o id é automático.) */
  isAuto(kind: ItemKind, id: string): boolean {
    return this.auto.has(key(kind, id));
  }

  replaceIn<L extends 'locations' | 'npcs' | 'factions'>(
    list: L,
    index: number,
    item: Campaign[L][number],
  ): void {
    this.update((c) => ({ ...c, [list]: replaceAt(c[list] as unknown[], index, item) }));
  }

  moveIn(list: 'locations' | 'npcs' | 'factions', index: number, delta: -1 | 1): void {
    this.update((c) => ({ ...c, [list]: moveAt(c[list] as unknown[], index, delta) }));
  }

  // --- conferência ----------------------------------------------------------------

  private scheduleValidation(delay: number): void {
    clearTimeout(this.timer);
    this.validating.set(true);
    this.timer = setTimeout(() => void this.validate(), delay);
  }

  private async validate(): Promise<void> {
    const campaign = this.campaign();
    if (campaign === null) {
      return;
    }
    const mine = ++this.sequence;
    try {
      const report = await firstValueFrom(this.api.editorValidate(campaign));
      if (mine === this.sequence) {
        this.report.set(report);
      }
    } catch (error) {
      if (mine === this.sequence) {
        this.report.set({
          ok: false,
          errors: [{ path: '', message: messageOf(error) }],
          findings: [],
        });
      }
    } finally {
      if (mine === this.sequence) {
        this.validating.set(false);
      }
    }
  }

  /** As frases de erro de um campo (`locations.0.name`) ou de tudo dentro dele (`locations.0`). */
  errorAt(path: string): string {
    const found = this.errors().find((e) => e.path === path || e.path.startsWith(`${path}.`));
    return found?.message ?? '';
  }

  // --- gravar ---------------------------------------------------------------------

  /** Prepara a gravação como cópia: id novo, e a campanha passa a ser nova. */
  startCopy(): void {
    const campaign = this.campaign();
    if (campaign === null) {
      return;
    }
    void firstValueFrom(this.api.editorCampaigns()).then((list) => {
      const id = freeIdIn(
        `${campaign.id}-copia`,
        list.map((c) => c.id),
      );
      this.savedId.set(null);
      this.writable.set(true);
      this.update((c) => ({ ...c, id, title: `${c.title} (cópia)` }));
    });
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
      this.markSaved(JSON.stringify(campaign));
      this.justSaved.set(true);
      if (savedId === null) {
        await this.router.navigate(['/editor', result.id], { replaceUrl: true });
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
    if (!this.dirty() || this.justSaved()) {
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

function freeIdIn(base: string, taken: readonly string[]): string {
  if (!taken.includes(base)) {
    return base;
  }
  for (let n = 2; ; n++) {
    if (!taken.includes(`${base}-${n}`)) {
      return `${base}-${n}`;
    }
  }
}
