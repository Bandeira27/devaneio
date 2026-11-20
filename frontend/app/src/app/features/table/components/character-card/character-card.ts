import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import type { Character, RulesView } from '@contract/api_responses';
import { DvKeyValue, type KeyValueItem } from '@shared/ui/key-value/key-value';
import { DvPips } from '@shared/ui/pips/pips';

/**
 * A ficha do personagem: pontos de vida, atributos e inventário (os itens que são armas aparecem pelo nome da arma).
 * Serve à folha "Ficha" e ao painel fixo da mesa larga. Só mostra: não tem estado, teclado nem movimento próprio
 * (os pontos de vida animam em `dv-pips`).
 */
@Component({
  selector: 'dv-character-card',
  imports: [DvKeyValue, DvPips],
  templateUrl: './character-card.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CharacterCard {
  readonly character = input.required<Character>();
  readonly rules = input.required<RulesView>();

  protected readonly items = computed<KeyValueItem[]>(() => {
    const character = this.character();
    const rules = this.rules();
    const weapon = (id: string): string => rules.weapons.find((w) => w.id === id)?.name ?? id;
    return [
      ...rules.attributes.map((a) => ({
        label: a.name,
        value: String(character.attributes[a.id] ?? '—'),
      })),
      {
        label: 'Inventário',
        value:
          character.inventory.length > 0 ? character.inventory.map(weapon).join(', ') : 'vazio',
      },
    ];
  });
}
