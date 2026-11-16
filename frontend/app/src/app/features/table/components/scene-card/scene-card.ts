import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import type { Scene } from '@shared/game/scene';

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
