import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { DvNotice } from '@shared/ui/notice/notice';
import { EditorStore } from '../editor.store';

/**
 * O que o servidor disse de um marco ou fato, junto dele: erros de integridade (por exemplo, uma condição que cita um
 * local que não existe mais) e avisos de autoria. O resumo lá em cima continua mostrando todos; aqui o autor vê o que
 * é deste item sem sair do formulário.
 */
@Component({
  selector: 'dv-item-problems',
  imports: [DvNotice],
  template: `
    @for (message of problems().errors; track $index) {
      <dv-notice kind="error">{{ message }}</dv-notice>
    }
    @for (finding of problems().findings; track $index) {
      <dv-notice [kind]="finding.level === 'erro' ? 'error' : 'warn'">{{ finding.text }}</dv-notice>
    }
  `,
  styles: ':host { display: grid; gap: var(--dv-space-2); } :host:empty { display: none; }',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ItemProblems {
  readonly word = input.required<'marco' | 'fato'>();
  readonly id = input.required<string>();
  private readonly store = inject(EditorStore);
  protected readonly problems = computed(() => this.store.problemsOf(this.word(), this.id()));
}
