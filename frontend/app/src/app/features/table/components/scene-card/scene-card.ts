import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DvKeyValue, type KeyValueItem } from '@shared/ui/key-value/key-value';
import type { Scene } from '@shared/game/scene';

const names = (list: readonly { name: string }[], none: string): string =>
  list.length > 0 ? list.map((item) => item.name).join(', ') : none;

/** O cartão da cena atual: local, descrição, saídas e quem está aqui. */
@Component({
  selector: 'dv-scene-card',
  imports: [DvKeyValue],
  templateUrl: './scene-card.html',
  styleUrl: './scene-card.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SceneCard {
  readonly scene = input.required<Scene>();
  protected readonly facts = computed<KeyValueItem[]>(() => [
    { label: 'Saídas', value: names(this.scene().exits, 'nenhuma') },
    { label: 'Aqui', value: names(this.scene().npcs, 'ninguém') },
  ]);
}
