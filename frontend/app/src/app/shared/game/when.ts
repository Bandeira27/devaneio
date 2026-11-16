const DAY = 24 * 60 * 60 * 1000;

/** Quando algo aconteceu, em palavras que cabem numa lista: "hoje", "ontem", "há 3 dias" ou a data. */
export function whenOf(time: number, now: number): string {
  const days = Math.round((startOfDay(now) - startOfDay(time)) / DAY);
  if (days <= 0) {
    return 'hoje';
  }
  if (days === 1) {
    return 'ontem';
  }
  if (days < 7) {
    return `há ${days} dias`;
  }
  return new Date(time).toLocaleDateString('pt-BR', { day: 'numeric', month: 'short' });
}

function startOfDay(time: number): number {
  const date = new Date(time);
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}
