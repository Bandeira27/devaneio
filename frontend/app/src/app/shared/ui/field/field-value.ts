/** O texto atual do campo (`input`, `textarea` ou `select`) que disparou o evento. */
export function fieldValue(event: Event): string {
  return (event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement).value;
}
