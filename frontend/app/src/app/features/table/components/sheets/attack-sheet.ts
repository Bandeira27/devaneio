import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';
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
 * Folha de atacar: escolhe alvo (o primeiro hostil já vem marcado) e arma, e confirma ali mesmo, porque atacar gasta
 * a ação. Devolve a linha de comando.
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
    } @else if (confirming()) {
      <p cdkFocusInitial tabindex="-1" #confirm>
        Atacar <strong>{{ targetName() }}</strong> com <strong>{{ weaponName() }}</strong>{{
          modifierName() ? ' (' + modifierName() + ')' : ''
        }}.
      </p>
      <p class="dv-note">Gasta a sua ação.</p>
      <div class="dv-sheet__foot">
        <button dvButton type="button" (click)="confirming.set(false)">Voltar</button>
        <button dvButton="primary" type="button" cdkFocusInitial (click)="ref.close(command())">
          Confirmar
        </button>
      </div>
    } @else {
      <form
        class="dv-stack"
        #form
        tabindex="-1"
        (submit)="$event.preventDefault(); confirming.set(true)"
      >
        <dv-choice legend="Alvo" [options]="targets()" [(value)]="target" />
        <dv-choice legend="Arma" [options]="weapons()" [(value)]="weapon" />
        @if (data.modifiers.length > 0) {
          <dv-choice legend="Modificador" [options]="modifiers()" [(value)]="modifier" />
        }
        <div class="dv-sheet__foot">
          <button dvButton="primary" type="submit">Atacar</button>
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
  protected readonly confirming = signal(false);
  private readonly injector = inject(Injector);
  private readonly confirm = viewChild<ElementRef<HTMLElement>>('confirm');
  private readonly form = viewChild<ElementRef<HTMLElement>>('form');

  constructor() {
    // Ao trocar de etapa o botão clicado some: o foco vai para o texto da confirmação ou, ao voltar, para o formulário.
    effect(() => {
      const confirming = this.confirming();
      afterNextRender(() => (confirming ? this.confirm() : this.form())?.nativeElement.focus(), {
        injector: this.injector,
      });
    });
  }

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
