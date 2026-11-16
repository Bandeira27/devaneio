import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { ModifierInfo, WeaponInfo } from '@contract/api_responses';
import { attack } from '@shared/game/commands';
import type { AttackTarget } from '@shared/game/rules';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';

/** O que a folha de atacar recebe: armas, alvos e modificadores. */
export interface AttackSheetData {
  weapons: WeaponInfo[];
  targets: AttackTarget[];
  modifiers: ModifierInfo[];
}

/** Folha de atacar: escolhe alvo e arma e devolve a linha de comando. */
@Component({
  selector: 'dv-attack-sheet',
  imports: [DvSheetHead, DvButton, DvField, DvInput],
  template: `
    <dv-sheet-head title="Atacar" />
    @if (data.targets.length === 0) {
      <p class="dv-note">Não há ninguém aqui para atacar.</p>
    } @else if (data.weapons.length === 0) {
      <p class="dv-note">Você não tem nenhuma arma.</p>
    } @else {
      <form class="dv-stack" (submit)="$event.preventDefault(); ref.close(command())">
        <dv-field label="Alvo">
          <select dvInput [value]="target()" (change)="target.set(fieldValue($event))">
            @for (item of data.targets; track item.id) {
              <option [value]="item.id">
                {{ item.name }} ({{ item.hp }}/{{ item.maxHp }}){{
                  item.hostile ? ' — hostil' : ''
                }}
              </option>
            }
          </select>
        </dv-field>
        <dv-field label="Arma" [hint]="damage()">
          <select dvInput [value]="weapon()" (change)="weapon.set(fieldValue($event))">
            @for (item of data.weapons; track item.id) {
              <option [value]="item.id">{{ item.name }}</option>
            }
          </select>
        </dv-field>
        @if (data.modifiers.length > 0) {
          <dv-field label="Modificador">
            <select dvInput [value]="modifier()" (change)="modifier.set(fieldValue($event))">
              <option value="">nenhum</option>
              @for (item of data.modifiers; track item.id) {
                <option [value]="item.id">{{ item.name }} ({{ item.value }})</option>
              }
            </select>
          </dv-field>
        }
        <button dvButton="primary" type="submit">Atacar</button>
      </form>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AttackSheet {
  protected readonly fieldValue = fieldValue;
  protected readonly data = inject(SHEET_DATA) as AttackSheetData;
  protected readonly ref = inject<SheetRef<string>>(SheetRef);

  protected readonly target = signal(this.data.targets[0]?.id ?? '');
  protected readonly weapon = signal(this.data.weapons[0]?.id ?? '');
  protected readonly modifier = signal('');
  protected readonly damage = computed(() => {
    const found = this.data.weapons.find((w) => w.id === this.weapon());
    return found ? `Dano ${found.damage}` : '';
  });
  protected readonly command = computed(() =>
    attack(this.weapon(), this.target(), this.modifier()),
  );
}
