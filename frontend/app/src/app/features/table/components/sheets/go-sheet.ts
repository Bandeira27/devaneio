import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { go } from '@shared/game/commands';
import { DvButton } from '@shared/ui/button/button';
import { SHEET_DATA, SheetRef } from '@shared/ui/sheet/sheet';
import { DvSheetHead } from '@shared/ui/sheet/sheet-head';

/** O que a folha de ir recebe: as saídas do local. */
export interface GoSheetData {
  exits: { id: string; name: string }[];
  /** O destino já escolhido (tocado na cena): a folha abre direto na confirmação. */
  preselect?: string;
}

/**
 * Folha de ir para outro local. Ir move o grupo todo e gasta a ação, então depois de escolher o destino a folha
 * pede a confirmação ali mesmo; devolve a linha de comando.
 */
@Component({
  selector: 'dv-go-sheet',
  imports: [DvSheetHead, DvButton],
  template: `
    <dv-sheet-head title="Ir" />
    @if (picked(); as exit) {
      <p class="dv-stack" cdkFocusInitial tabindex="-1" #confirm>
        Mover o grupo para <strong>{{ exit.name }}</strong>. Gasta a sua ação.
      </p>
      <div class="dv-sheet__foot">
        <button dvButton type="button" (click)="picked.set(null)">Voltar</button>
        <button
          dvButton="primary"
          type="button"
          cdkFocusInitial
          (click)="ref.close(command(exit.id))"
        >
          Confirmar
        </button>
      </div>
    } @else {
      @if (data.exits.length === 0) {
        <p class="dv-note">Não há saídas daqui.</p>
      }
      <div class="dv-stack" #list tabindex="-1">
        @for (exit of data.exits; track exit.id) {
          <button
            dvButton
            type="button"
            [attr.cdkFocusInitial]="$first ? '' : null"
            (click)="picked.set(exit)"
          >
            {{ exit.name }}
          </button>
        }
      </div>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GoSheet {
  protected readonly data = inject(SHEET_DATA) as GoSheetData;
  protected readonly ref = inject<SheetRef<string>>(SheetRef);
  protected readonly picked = signal<{ id: string; name: string } | null>(
    this.data.exits.find((exit) => exit.id === this.data.preselect) ?? null,
  );
  private readonly injector = inject(Injector);
  private readonly confirm = viewChild<ElementRef<HTMLElement>>('confirm');
  private readonly list = viewChild<ElementRef<HTMLElement>>('list');

  constructor() {
    // Trocar de etapa remove o botão clicado: o foco vai para o texto da confirmação (não para "Confirmar", que
    // gasta a ação) ou, ao voltar, para a lista.
    effect(() => {
      const picked = this.picked();
      afterNextRender(() => (picked ? this.confirm() : this.list())?.nativeElement.focus(), {
        injector: this.injector,
      });
    });
  }

  protected command(id: string): string {
    return go(id);
  }
}
