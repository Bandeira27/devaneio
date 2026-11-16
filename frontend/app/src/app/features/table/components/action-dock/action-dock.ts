import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { DvButton } from '@shared/ui/button/button';
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
  imports: [DvButton, DvNotice],
  templateUrl: './action-dock.html',
  styleUrl: './action-dock.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ActionDock {
  protected readonly store = inject(TableStore);
  private readonly sheet = inject(Sheet);

  protected async go(): Promise<void> {
    const line = await this.sheet.open<string>(GoSheet, {
      label: 'Ir para',
      data: { exits: this.store.scene()?.exits ?? [] },
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
      label: 'Testar uma habilidade',
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
        label: 'Ficha do personagem',
        data: { character, rules },
      });
    }
  }

  protected async say(): Promise<void> {
    const text = await this.sheet.open<string>(SaySheet, { label: 'Falar com o mestre' });
    if (text) {
      await this.store.say(text);
    }
  }

  protected async command(): Promise<void> {
    const line = await this.sheet.open<string>(CommandSheet, { label: 'Digitar um comando' });
    if (line) {
      await this.store.run(line);
    }
  }
}
