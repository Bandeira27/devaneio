import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { SessionStore } from '@core/session/session-store';
import { describeInvite } from '@shared/game/invite';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvCopyField } from '@shared/ui/copy-field/copy-field';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { DvIcon } from '@shared/ui/icon/icon';
import { DvNotice } from '@shared/ui/notice/notice';
import { TableStore } from '../../table.store';

/** De quanto em quanto tempo (ms) a sala relê a mesa: entrar na mesa e criar personagem não geram evento. */
export const LOBBY_REFRESH_MS = 4000;

/**
 * A sala de espera: o que se vê antes de a história começar. O anfitrião vê o convite, quem já entrou (e com que
 * personagem) e o botão **Iniciar campanha**; quem foi convidado vê quem já está aqui e espera. Todos podem criar o seu
 * personagem. A lista se atualiza sozinha enquanto a sala está aberta.
 */
@Component({
  selector: 'dv-lobby',
  imports: [
    RouterLink,
    DvBadge,
    DvButton,
    DvCopyField,
    DvDisclosure,
    DvField,
    DvIcon,
    DvInput,
    DvNotice,
  ],
  templateUrl: './lobby.html',
  styleUrl: './lobby.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Lobby {
  /** O id da mesa, da rota. */
  readonly tableId = input.required<string>();

  protected readonly store = inject(TableStore);
  private readonly session = inject(SessionStore);
  protected readonly fieldValue = fieldValue;

  /** O endereço que os outros aparelhos alcançam (começa no deste aparelho). */
  protected readonly addressText = signal(globalThis.location.origin);
  protected readonly advancedOpen = signal(false);
  private readonly invite = computed(() =>
    describeInvite(
      this.addressText(),
      this.tableId(),
      this.session.get(this.tableId())?.invite ?? null,
    ),
  );
  protected readonly link = computed(() => this.invite().link);
  protected readonly addressError = computed(() => this.invite().error);
  protected readonly localWarning = computed(() => this.invite().localWarning);

  /** Quem está na sala: cada jogador com os nomes dos personagens que já criou. */
  protected readonly people = computed(() => {
    const table = this.store.table();
    const characters = table?.state.characters ?? {};
    return (table?.players ?? []).map((player) => ({
      id: player.id,
      name: player.name,
      host: player.role === 'host',
      you: player.id === table?.you,
      characters: player.character_ids.map((id) => characters[id]?.name ?? id),
    }));
  });
  protected readonly hasCharacters = computed(() => this.store.party().length > 0);
  /** Por que ainda não dá para iniciar, ou `''`. */
  protected readonly startBlock = computed(() =>
    this.hasCharacters() ? '' : 'Crie ao menos um personagem para iniciar.',
  );

  constructor() {
    effect((onCleanup) => {
      const timer = setInterval(() => void this.store.refresh(), LOBBY_REFRESH_MS);
      onCleanup(() => clearInterval(timer));
    });
    effect(() => {
      // O aviso de endereço local abre as opções, onde está o conserto, e elas não fecham sozinhas.
      if (this.localWarning() || this.addressError() !== '') {
        this.advancedOpen.set(true);
      }
    });
  }

  protected start(): void {
    void this.store.lifecycle('start');
  }
}
