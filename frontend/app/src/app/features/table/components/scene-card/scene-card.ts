import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { DvButton } from '@shared/ui/button/button';
import { DvIcon } from '@shared/ui/icon/icon';
import { DvKeyValue, type KeyValueItem } from '@shared/ui/key-value/key-value';
import type { Scene } from '@shared/game/scene';

const names = (list: readonly { name: string }[], none: string): string =>
  list.length > 0 ? list.map((item) => item.name).join(', ') : none;

/**
 * O cartão da cena atual: local, quem está aqui, as saídas (cada uma um botão que pede para ir até lá; a confirmação é da
 * folha de `Ir`) e a descrição. `canGo` bloqueia as saídas quando agir não é possível (o motivo está na barra de ações).
 */
@Component({
  selector: 'dv-scene-card',
  imports: [DvButton, DvIcon, DvKeyValue],
  templateUrl: './scene-card.html',
  styleUrl: './scene-card.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SceneCard {
  readonly scene = input.required<Scene>();
  /** Dá para agir agora? Sem isso as saídas ficam bloqueadas. */
  readonly canGo = input(true);
  /** O id do texto que diz por que não dá para agir (ligado às saídas bloqueadas por `aria-describedby`), se houver. */
  readonly blockedReasonId = input<string | null>(null);
  /** O id da saída que a pessoa tocou. */
  readonly exitChosen = output<string>();
  /** Quem está na cena; sem ninguém, a linha nem aparece (em vez de "ninguém" solto). */
  protected readonly facts = computed<KeyValueItem[]>(() =>
    this.scene().npcs.length === 0
      ? []
      : [{ label: 'Presentes', value: names(this.scene().npcs, '') }],
  );
}
