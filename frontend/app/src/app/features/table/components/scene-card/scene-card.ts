import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvKeyValue, type KeyValueItem } from '@shared/ui/key-value/key-value';
import { isWide } from '@shared/ui/wide';
import type { Scene } from '@shared/game/scene';

const names = (list: readonly { name: string }[], none: string): string =>
  list.length > 0 ? list.map((item) => item.name).join(', ') : none;

/** O cartão da cena atual: local, descrição, saídas e quem está aqui. */
@Component({
  selector: 'dv-scene-card',
  imports: [DvDisclosure, DvKeyValue],
  templateUrl: './scene-card.html',
  styleUrl: './scene-card.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SceneCard {
  readonly scene = input.required<Scene>();
  /** Na tela larga (a coluna lateral) a descrição já nasce aberta; no celular, recolhida para a cena ocupar pouco. */
  protected readonly wide = isWide();
  protected readonly facts = computed<KeyValueItem[]>(() => [
    { label: 'Saídas', value: names(this.scene().exits, 'nenhuma') },
    { label: 'Aqui', value: names(this.scene().npcs, 'ninguém') },
  ]);
}
