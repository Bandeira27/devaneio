import { ConfirmSheet } from '@shared/ui/confirm/confirm-sheet';
import type { Sheet } from '@shared/ui/sheet/sheet';

/** Pergunta se pode remover um item (um local, um NPC...), dizendo o que some junto; `true` se o autor confirmou. */
export async function confirmRemove(sheet: Sheet, title: string, text: string): Promise<boolean> {
  const ok = await sheet.open<boolean>(ConfirmSheet, {
    label: title,
    data: { title, text, action: 'Remover' },
  });
  return ok === true;
}
