import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import type { FactDef } from '@contract/api_responses';
import { replaceAt } from '@shared/game/campaign-edit';
import { DvListEditor } from '@shared/ui/list-editor/list-editor';
import { DvSelect, type SelectOption } from '@shared/ui/select/select';
import { Sheet } from '@shared/ui/sheet/sheet';
import { ConditionsEditor } from '../components/conditions-editor';
import { confirmRemove } from '../components/confirm-remove';
import { ItemProblems } from '../components/item-problems';
import { NameIdFields } from '../components/name-id-fields';
import { EditorStore } from '../editor.store';

const SHORT = 40;

/**
 * Os fatos: verdades da campanha que os jogadores ainda não conhecem. Cada um pode falar de um item (local, NPC,
 * facção ou marco) e ser revelado sozinho quando as condições valem; sem condições, só o anfitrião o revela. Um fato
 * escrito aqui nunca chega ao jogador nem ao LLM antes de ser revelado.
 */
@Component({
  selector: 'dv-facts-section',
  imports: [ConditionsEditor, DvListEditor, DvSelect, ItemProblems, NameIdFields],
  templateUrl: './facts-section.html',
  styleUrl: './editor-sections.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FactsSection {
  protected readonly store = inject(EditorStore);
  private readonly sheet = inject(Sheet);
  protected readonly nameOf = (fact: FactDef): string =>
    fact.text.length > SHORT ? `${fact.text.slice(0, SHORT)}…` : fact.text || fact.id;
  /** Os itens de que um fato pode falar, com o tipo no rótulo. */
  protected readonly subjects = computed<SelectOption[]>(() => {
    const c = this.store.campaign();
    const label = (kind: string, name: string, id: string): string => `${kind}: ${name || id}`;
    return [
      { value: '', label: '(nada em particular)' },
      ...(c?.locations ?? []).map((l) => ({ value: l.id, label: label('Local', l.name, l.id) })),
      ...(c?.npcs ?? []).map((n) => ({ value: n.id, label: label('NPC', n.name, n.id) })),
      ...(c?.factions ?? []).map((f) => ({ value: f.id, label: label('Facção', f.name, f.id) })),
      ...(c?.beats ?? []).map((b) => ({ value: b.id, label: label('Marco', b.title, b.id) })),
    ];
  });

  /** O texto do fato; o id acompanha as primeiras palavras enquanto o autor não o escreve. */
  protected setText(index: number, fact: FactDef, text: string): void {
    this.store.rename('fact', fact.id, text, (c) => ({
      ...c,
      facts: replaceAt(c.facts, index, { ...fact, text }),
    }));
  }

  protected patch(index: number, fact: FactDef, patch: Partial<FactDef>): void {
    this.store.replaceIn('facts', index, { ...fact, ...patch });
  }

  protected async remove(index: number): Promise<void> {
    const fact = this.store.campaign()?.facts[index];
    if (fact === undefined) {
      return;
    }
    const ok = await confirmRemove(
      this.sheet,
      'Remover o fato',
      `Remover "${this.nameOf(fact)}"? Ele deixa de existir na campanha.`,
    );
    if (ok) {
      this.store.remove('fact', fact.id);
    }
  }
}
