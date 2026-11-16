import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import type { Scene } from '@shared/game/scene';

/** O cartão da cena atual: local, descrição, saídas e quem está aqui. */
@Component({
  selector: 'dv-scene-card',
  templateUrl: './scene-card.html',
  styleUrl: './scene-card.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SceneCard {
  readonly scene = input.required<Scene>();

  protected names(list: readonly { name: string }[]): string {
    return list.map((item) => item.name).join(', ');
  }
}
