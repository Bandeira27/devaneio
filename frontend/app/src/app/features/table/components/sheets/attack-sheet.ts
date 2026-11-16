import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { ModifierInfo, WeaponInfo } from '@contract/api_responses';
import { attack } from '@shared/game/commands';
import type { AttackTarget } from '@shared/game/rules';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { DvInput } from '@shared/ui/field/input';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';

export interface AttackSheetData {
  weapons: WeaponInfo[];
  targets: AttackTarget[];
  modifiers: ModifierInfo[];
}

@Component({
  selector: 'dv-attack-sheet',
  imports: [DvButton, DvField, DvInput],
  template: `
    <div class="dv-sheet__head">
      <h2 class="dv-title">Atacar</h2>
      <button dvButton type="button" (click)="ref.close()">Fechar</button>
    </div>
    @if (data.targets.length === 0) {
      <p class="dv-note">Não há ninguém aqui para atacar.</p>
    } @else if (data.weapons.length === 0) {
      <p class="dv-note">Você não tem nenhuma arma.</p>
    } @else {
      <form class="dv-stack" (submit)="$event.preventDefault(); ref.close(command())">
        <dv-field label="Alvo">
          <select dvInput [value]="target()" (change)="target.set(value($event))">
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
          <select dvInput [value]="weapon()" (change)="weapon.set(value($event))">
            @for (item of data.weapons; track item.id) {
              <option [value]="item.id">{{ item.name }}</option>
            }
          </select>
        </dv-field>
        @if (data.modifiers.length > 0) {
          <dv-field label="Modificador">
            <select dvInput [value]="modifier()" (change)="modifier.set(value($event))">
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

  protected value(event: Event): string {
    return (event.target as HTMLSelectElement).value;
  }
}
