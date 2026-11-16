import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import type { Character } from '@contract/api_responses';
import { DvPips } from '@shared/ui/pips/pips';

/** A faixa do grupo: cada personagem com o hp em pontos. */
@Component({
  selector: 'dv-party-strip',
  imports: [DvPips],
  templateUrl: './party-strip.html',
  styleUrl: './party-strip.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PartyStrip {
  readonly characters = input.required<readonly Character[]>();
  /** O personagem de quem olha: aparece marcado. */
  readonly mine = input<string | null>(null);
  readonly acted = input<Readonly<Record<string, number>>>({});
  readonly turn = input(0);
}
