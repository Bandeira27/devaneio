/** O texto atual do campo (`input`, `textarea` ou `select`) que disparou o evento. */
export function valueOf(event: Event): string {
  return (event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement).value;
}
