import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type { LlmSettingsView } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { ApiFailure, messageOf } from '@core/api/api-failure';
import { ConfirmSheet, type ConfirmSheetData } from '@shared/ui/confirm/confirm-sheet';
import { Sheet } from '@shared/ui/sheet/sheet';

/** O tempo que o servidor usa quando a tela não diz outro, em segundos. */
export const DEFAULT_TIMEOUT = 60;
const MIN_TIMEOUT = 1;
const MAX_TIMEOUT = 600;

const CLEAR_KEY_CONFIRM: ConfirmSheetData = {
  title: 'Apagar a chave',
  text: 'A chave guardada neste computador será apagada e não dá para vê-la de novo. O endereço e o modelo ficam.',
  action: 'Apagar a chave',
};
const CLEAR_ALL_CONFIRM: ConfirmSheetData = {
  title: 'Remover a configuração',
  text: 'O endereço, o modelo e a chave guardados aqui serão apagados. Se houver um LLM nas variáveis de ambiente, ele volta a valer; senão o jogo segue só com o motor.',
  action: 'Remover',
};

/** O que a tela mostra enquanto fala com o servidor: carregando, pronta, só neste computador ou falhou. */
export type SettingsState = 'loading' | 'ready' | 'unavailable' | 'failed';

/** O resultado do último "Testar conexão": `ok` ou a frase fixa do servidor. */
export interface TestOutcome {
  ok: boolean;
  message: string;
}

/**
 * A configuração do LLM da máquina: carrega o que o servidor guarda, valida o formulário, salva e testa. A chave só vai
 * no envio e nunca volta: o servidor diz apenas se existe uma (`keySet`), e o campo nunca é preenchido de volta.
 */
@Injectable()
export class LlmSettingsStore {
  private readonly api = inject(ApiClient);
  private readonly sheet = inject(Sheet);

  readonly state = signal<SettingsState>('loading');
  readonly loadError = signal('');
  readonly view = signal<LlmSettingsView | null>(null);

  readonly baseUrl = signal('');
  readonly model = signal('');
  readonly timeout = signal(String(DEFAULT_TIMEOUT));
  /** A chave digitada agora; vazia = manter a atual. */
  readonly apiKey = signal('');

  readonly urlError = signal('');
  readonly modelError = signal('');
  readonly timeoutError = signal('');
  readonly saveError = signal('');
  readonly saved = signal(false);
  readonly saving = signal(false);
  readonly testing = signal(false);
  readonly outcome = signal<TestOutcome | null>(null);
  /** Qual remoção está em andamento (só aquele botão mostra o envio), ou nenhuma. */
  readonly removing = signal<'key' | 'all' | null>(null);
  /** O erro de uma remoção, mostrado junto dos botões de remover (e não lá em cima, no formulário). */
  readonly removeError = signal('');
  /** O que acabou de ser removido, para anunciar: o botão que o usuário tocou some junto. */
  readonly removed = signal('');
  /** Há algo em andamento? Enquanto sim, os botões esperam, para um envio não atropelar o outro. */
  readonly busy = computed(() => this.saving() || this.testing() || this.removing() !== null);
  /** O endereço digitado não é deste computador: o texto e o estado das mesas saem dele. */
  readonly remote = computed(() => isRemote(this.baseUrl().trim()));

  readonly keySet = computed(() => this.view()?.key_set ?? false);
  readonly source = computed(() => this.view()?.source ?? 'none');
  /** Há algo guardado pela tela (e não só o que vem do ambiente)? */
  readonly hasScreenConfig = computed(() => (this.view()?.base_url ?? null) !== null);

  async load(): Promise<void> {
    this.state.set('loading');
    this.loadError.set('');
    try {
      this.apply(await firstValueFrom(this.api.editorLlmSettings()));
      this.state.set('ready');
    } catch (error) {
      if (error instanceof ApiFailure && error.status === 404) {
        this.state.set('unavailable'); // de fora da máquina do servidor, ou com --sem-editor
        return;
      }
      this.loadError.set(messageOf(error));
      this.state.set('failed');
    }
  }

  setBaseUrl(value: string): void {
    this.baseUrl.set(value);
    this.urlError.set('');
    this.touched();
  }

  setModel(value: string): void {
    this.model.set(value);
    this.modelError.set('');
    this.touched();
  }

  setTimeoutSeconds(value: string): void {
    this.timeout.set(value);
    this.timeoutError.set('');
    this.touched();
  }

  setApiKey(value: string): void {
    this.apiKey.set(value);
    this.touched();
  }

  /** Qual campo tem erro agora, na ordem da tela, para a página levar o foco até ele; nada se não há erro. */
  firstInvalid(): 'url' | 'model' | 'timeout' | null {
    if (this.urlError() !== '') {
      return 'url';
    }
    if (this.modelError() !== '') {
      return 'model';
    }
    return this.timeoutError() !== '' ? 'timeout' : null;
  }

  async save(): Promise<boolean> {
    if (this.busy()) {
      return false;
    }
    const baseUrl = this.baseUrl().trim();
    const model = this.model().trim();
    const timeout = parseTimeout(this.timeout());
    this.urlError.set(validateUrl(baseUrl));
    this.modelError.set(model === '' ? 'Escreva o nome do modelo.' : '');
    this.timeoutError.set(
      timeout !== null && timeout >= MIN_TIMEOUT && timeout <= MAX_TIMEOUT
        ? ''
        : `Use um número de ${MIN_TIMEOUT} a ${MAX_TIMEOUT} segundos.`,
    );
    this.saveError.set('');
    this.removed.set('');
    if (this.firstInvalid() !== null) {
      return false;
    }
    this.saving.set(true);
    try {
      const key = this.apiKey().trim();
      this.apply(
        await firstValueFrom(
          this.api.editorSaveLlmSettings({
            base_url: baseUrl,
            model,
            timeout: timeout ?? DEFAULT_TIMEOUT,
            ...(key === '' ? {} : { api_key: key }),
          }),
        ),
      );
      this.saved.set(true);
      return true;
    } catch (error) {
      this.saveError.set(messageOf(error));
      return false;
    } finally {
      this.saving.set(false);
    }
  }

  /** Guarda o que está no formulário e, se guardou, testa a conexão. Diz se guardou. */
  async saveAndTest(): Promise<boolean> {
    const saved = await this.save();
    if (saved) {
      await this.test();
    }
    return saved;
  }

  async test(): Promise<void> {
    if (this.testing() || this.saving() || this.removing() !== null) {
      return;
    }
    this.testing.set(true);
    this.outcome.set(null);
    try {
      this.outcome.set(await firstValueFrom(this.api.editorTestLlm()));
    } catch (error) {
      this.outcome.set({ ok: false, message: messageOf(error) });
    } finally {
      this.testing.set(false);
    }
  }

  /** Apaga só a chave guardada, depois de confirmar: não tem como vê-la de novo. Diz se apagou. */
  async clearKey(): Promise<boolean> {
    return (
      !this.busy() &&
      (await this.confirm(CLEAR_KEY_CONFIRM)) &&
      this.remove('key', 'A chave foi apagada.', () => this.api.editorClearLlmKey())
    );
  }

  /** Apaga o que a tela guardou, chave inclusive, depois de confirmar. Diz se apagou. */
  async clearAll(): Promise<boolean> {
    return (
      !this.busy() &&
      (await this.confirm(CLEAR_ALL_CONFIRM)) &&
      this.remove('all', 'A configuração foi removida.', () => this.api.editorClearLlmSettings())
    );
  }

  private async confirm(data: ConfirmSheetData): Promise<boolean> {
    return (await this.sheet.open<boolean>(ConfirmSheet, { label: data.title, data })) === true;
  }

  private async remove(
    which: 'key' | 'all',
    done: string,
    call: () => ReturnType<ApiClient['editorClearLlmKey']>,
  ): Promise<boolean> {
    this.removing.set(which);
    this.removeError.set('');
    this.removed.set('');
    try {
      this.apply(await firstValueFrom(call()));
      this.saved.set(false);
      this.outcome.set(null);
      this.removed.set(done);
      return true;
    } catch (error) {
      this.removeError.set(messageOf(error));
      return false;
    } finally {
      this.removing.set(null);
    }
  }

  /** Põe o que o servidor guardou no formulário. A chave nunca volta, então o campo dela fica vazio. */
  private apply(view: LlmSettingsView): void {
    this.view.set(view);
    this.baseUrl.set(view.base_url ?? '');
    this.model.set(view.model ?? '');
    this.timeout.set(String(view.timeout ?? DEFAULT_TIMEOUT));
    this.apiKey.set('');
  }

  private touched(): void {
    this.saved.set(false);
    this.outcome.set(null);
    this.removed.set('');
  }
}

/** O texto de erro do endereço, ou vazio se está bom. Mesmas regras do servidor (que confere de novo). */
export function validateUrl(value: string): string {
  if (value === '') {
    return 'Escreva o endereço do servidor.';
  }
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return 'O endereço precisa começar com http:// ou https://.';
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    return 'O endereço precisa começar com http:// ou https://.';
  }
  if (url.username !== '' || url.password !== '') {
    return 'O endereço não pode ter usuário e senha: a chave vai no campo próprio.';
  }
  if (url.search !== '' || url.hash !== '') {
    return 'O endereço não pode ter parâmetros nem âncora.';
  }
  return '';
}

/** O tempo digitado em segundos (aceita vírgula decimal), `DEFAULT_TIMEOUT` se vazio, ou `null` se não é número. */
export function parseTimeout(raw: string): number | null {
  const text = raw.trim();
  if (text === '') {
    return DEFAULT_TIMEOUT;
  }
  return /^\d+([.,]\d+)?$/.test(text) ? Number(text.replace(',', '.')) : null;
}

/** O endereço aponta para fora deste computador? Endereço que não se lê vale como "não sei": sem aviso. */
export function isRemote(value: string): boolean {
  try {
    const host = new URL(value).hostname;
    return (
      !['localhost', '127.0.0.1', '[::1]', '::1'].includes(host) && !host.endsWith('.localhost')
    );
  } catch {
    return false;
  }
}
