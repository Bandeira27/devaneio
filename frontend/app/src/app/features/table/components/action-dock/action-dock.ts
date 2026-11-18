import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  viewChild,
} from '@angular/core';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvIcon } from '@shared/ui/icon/icon';
import { DvNotice } from '@shared/ui/notice/notice';
import { Sheet } from '@shared/ui/sheet/sheet';
import { TableStore } from '../../table.store';
import { AttackSheet } from '../sheets/attack-sheet';
import { CharacterSheet } from '../sheets/character-sheet';
import { CheckSheet } from '../sheets/check-sheet';
import { CommandSheet } from '../sheets/command-sheet';
import { GoSheet } from '../sheets/go-sheet';
import { SaySheet } from '../sheets/say-sheet';

/** As ações da mesa em botões. Cada uma abre uma folha, monta a linha de comando e o servidor decide. */
@Component({
  selector: 'dv-action-dock',
  imports: [DvBadge, DvButton, DvIcon, DvNotice],
  templateUrl: './action-dock.html',
  styleUrl: './action-dock.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ActionDock {
  protected readonly store = inject(TableStore);
  private readonly sheet = inject(Sheet);
  private readonly root = viewChild.required<ElementRef<HTMLElement>>('root');

  /**
   * O motivo do bloqueio já está dito, em destaque, num aviso no alto da mesa (conexão perdida, fim da partida): aqui
   * ele só fica ligado aos botões (leitor de tela), sem repetir o texto à vista.
   */
  protected readonly reasonSaidAbove = computed(() => {
    const live = this.store.liveStatus();
    const status = this.store.status();
    return live === 'expired' || live === 'gone' || status === 'won' || status === 'lost';
  });

  /** Por que Ir não serve agora (a cena já é conhecida e não tem saída), ou `''`. */
  protected readonly goReason = computed(() =>
    this.store.scene()?.exits.length === 0 ? 'Não há saídas daqui.' : '',
  );
  /** Por que Atacar não serve agora (ninguém para atacar, ou sem arma), ou `''`. */
  protected readonly attackReason = computed(() => {
    if (this.store.character() === null) {
      return ''; // sem personagem o motivo é outro, e o bloqueio geral já o diz
    }
    if (this.store.targets().length === 0) {
      return 'Não há ninguém aqui para atacar.';
    }
    return this.store.weapons().length === 0 ? 'Você não tem nenhuma arma.' : '';
  });
  /** Os motivos de Ir e Atacar, numa frase só, para ligar aos botões (só vale quando não há bloqueio geral). */
  protected readonly actReason = computed(() =>
    [this.goReason(), this.attackReason()].filter(Boolean).join(' '),
  );

  /**
   * Leva o foco ao primeiro botão que ainda age, das ações do turno antes das de apoio, e que esteja à vista (o botão
   * "Ficha" some na tela muito larga). Se não há nenhum, o foco vai para a própria barra.
   */
  focusActions(): void {
    const root = this.root().nativeElement;
    const acts = "button:not([disabled]):not([aria-disabled='true'])";
    const candidates = [
      ...root.querySelectorAll<HTMLElement>(`.dock__main ${acts}`),
      ...root.querySelectorAll<HTMLElement>(`.dock__minor ${acts}`),
    ];
    const first = candidates.find((el) => el.checkVisibility?.() !== false);
    (first ?? root).focus();
  }

  /** Tira a resposta ou o erro da tela e devolve o foco às ações (o botão de dispensar some junto). */
  protected dismissFeedback(): void {
    this.store.dismissFeedback();
    queueMicrotask(() => this.focusActions());
  }

  /** Abre a folha de `Ir`; com `exitId` (uma saída tocada na cena) ela já abre na confirmação desse destino. */
  async go(exitId?: string): Promise<void> {
    const line = await this.sheet.open<string>(GoSheet, {
      label: 'Ir',
      data: { exits: this.store.scene()?.exits ?? [], preselect: exitId },
    });
    if (line) {
      await this.store.run(line);
    }
  }

  protected async check(): Promise<void> {
    const rules = this.store.rules();
    if (rules === null) {
      return;
    }
    const line = await this.sheet.open<string>(CheckSheet, {
      label: 'Testar',
      data: { rules },
    });
    if (line) {
      await this.store.run(line);
    }
  }

  protected async attack(): Promise<void> {
    const rules = this.store.rules();
    if (rules === null) {
      return;
    }
    const line = await this.sheet.open<string>(AttackSheet, {
      label: 'Atacar',
      data: {
        weapons: this.store.weapons(),
        targets: this.store.targets(),
        modifiers: rules.modifiers,
      },
    });
    if (line) {
      await this.store.run(line);
    }
  }

  protected async sheetOfCharacter(): Promise<void> {
    const character = this.store.character();
    const rules = this.store.rules();
    if (character !== null && rules !== null) {
      await this.sheet.open(CharacterSheet, {
        label: `Ficha de ${character.name}`,
        data: { character, rules },
      });
    }
  }

  protected async say(): Promise<void> {
    const text = await this.sheet.open<string>(SaySheet, { label: 'Falar' });
    if (text) {
      await this.store.say(text);
    }
  }

  protected async command(): Promise<void> {
    const line = await this.sheet.open<string>(CommandSheet, { label: 'Comando' });
    if (line) {
      await this.store.run(line);
    }
  }
}
