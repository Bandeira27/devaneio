import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { ModifierInfo, WeaponInfo } from '@contract/api_responses';
import { modifierOptions } from '@shared/game/modifiers';
import { attack } from '@shared/game/commands';
import type { AttackTarget } from '@shared/game/rules';
import { DvButton } from '@shared/ui/button/button';
import { DvChoice, type ChoiceOption } from '@shared/ui/choice/choice';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';

/** O que a folha de atacar recebe: armas, alvos e modificadores. */
export interface AttackSheetData {
  weapons: WeaponInfo[];
  targets: AttackTarget[];
  modifiers: ModifierInfo[];
}

/**
 * Folha de atacar, em um passo: alvo (o primeiro hostil já vem marcado), arma e modificador, e o botão do rodapé diz
 * quem será atacado; atacar gasta a ação, e a nota avisa. Devolve a linha de comando.
 */
@Component({
  selector: 'dv-attack-sheet',
  imports: [DvSheetHead, DvButton, DvChoice],
  template: `
    <dv-sheet-head title="Atacar" />
    @if (data.targets.length === 0) {
      <p class="dv-note">Não há ninguém aqui para atacar.</p>
    } @else if (data.weapons.length === 0) {
      <p class="dv-note">Você não tem nenhuma arma.</p>
    } @else {
      <form
        class="dv-stack"
        #form
        tabindex="-1"
        (submit)="$event.preventDefault(); ref.close(command())"
      >
        <dv-choice legend="Alvo" [options]="targets()" [(value)]="target" />
        <dv-choice legend="Arma" [options]="weapons()" [(value)]="weapon" />
        @if (data.modifiers.length > 0) {
          <dv-choice legend="Modificador" [options]="modifiers()" [(value)]="modifier" />
        }
        <p class="dv-note">Gasta a sua ação.</p>
        <div class="dv-sheet__foot">
          <button dvButton type="button" (click)="ref.close()">Cancelar</button>
          <button dvButton="primary" type="submit">Atacar {{ targetName() }}</button>
        </div>
      </form>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AttackSheet {
  protected readonly data = inject(SHEET_DATA) as AttackSheetData;
  protected readonly ref = inject<SheetRef<string>>(SheetRef);

  protected readonly target = signal(
    (this.data.targets.find((t) => t.hostile) ?? this.data.targets[0])?.id ?? '',
  );
  protected readonly weapon = signal(this.data.weapons[0]?.id ?? '');
  protected readonly modifier = signal('');

  protected readonly targets = computed<ChoiceOption[]>(() =>
    this.data.targets.map((t) => ({
      value: t.id,
      label: t.name,
      detail: `${t.hp}/${t.maxHp} de vida${t.hostile ? ' · hostil' : ''}`,
    })),
  );
  protected readonly weapons = computed<ChoiceOption[]>(() =>
    this.data.weapons.map((w) => ({ value: w.id, label: w.name, detail: `Dano ${w.damage}` })),
  );
  protected readonly modifiers = computed(() => modifierOptions(this.data.modifiers));
  protected readonly targetName = computed(
    () => this.data.targets.find((t) => t.id === this.target())?.name ?? '',
  );
  protected readonly modifierName = computed(
    () => this.data.modifiers.find((m) => m.id === this.modifier())?.name ?? '',
  );
  protected readonly weaponName = computed(
    () => this.data.weapons.find((w) => w.id === this.weapon())?.name ?? '',
  );
  protected readonly command = computed(() =>
    attack(this.weapon(), this.target(), this.modifier()),
  );
}
