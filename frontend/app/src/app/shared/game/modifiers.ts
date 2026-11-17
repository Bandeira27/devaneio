import type { ModifierInfo } from '@contract/api_responses';
import type { ChoiceOption } from './choice-option';

/** As opções de modificador de um teste ou ataque: "Nenhum" primeiro, depois cada um com o valor com sinal. */
export function modifierOptions(modifiers: readonly ModifierInfo[]): ChoiceOption[] {
  return [
    { value: '', label: 'Nenhum' },
    ...modifiers.map((m) => ({
      value: m.id,
      label: m.name,
      detail: m.value > 0 ? `+${m.value}` : String(m.value),
    })),
  ];
}
