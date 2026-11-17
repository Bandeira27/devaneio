/**
 * O foco está livre? Vale quando nada tem foco (ou só o `<body>`, ou um elemento que já saiu da tela) ou, dado
 * `within`, quando o foco está fora dessa região ou na própria região. Serve para devolver o foco a um lugar sensato
 * sem roubá-lo de quem já está digitando num campo.
 */
export function isFocusFree(within?: HTMLElement): boolean {
  const active = document.activeElement;
  if (active === null || active === document.body || !active.isConnected) {
    return true;
  }
  return within !== undefined && (active === within || !within.contains(active));
}

/** Leva o foco a um elemento que não é focável por natureza (um título, uma região) sem rolar a tela. */
export function focusElement(element: HTMLElement): void {
  element.tabIndex = -1;
  element.focus({ preventScroll: true });
}
