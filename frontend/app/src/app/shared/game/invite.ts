/** O convite de uma mesa: o link `/#/entrar/<mesa>/<código>`. Tudo isso fica no fragmento: nunca vai ao servidor nem ao log. */

/** A mesa e o código que vêm no link de convite. */
export interface Invite {
  tableId: string;
  code: string;
}

const TABLE_ID = /^[a-f0-9]{16}$/;
const CODE = /^[A-Za-z0-9_-]{1,64}$/;
const IN_LINK = /entrar\/([a-f0-9]{16})\/([A-Za-z0-9_-]{1,64})(?![A-Za-z0-9_-])/;
const PAIR = /^([a-f0-9]{16})[\s/:]+([A-Za-z0-9_-]{1,64})$/;

/** Se o texto tem o formato de id de mesa que o servidor gera. */
export function isTableId(text: string): boolean {
  return TABLE_ID.test(text);
}

/** Se o texto tem o formato de código de convite. */
export function isInviteCode(text: string): boolean {
  return CODE.test(text);
}

/** Lê um link de convite (inteiro ou só a parte do fragmento) ou o par `mesa código`; `null` se não parecer um. */
export function parseInvite(text: string): Invite | null {
  const trimmed = text.trim();
  const found = IN_LINK.exec(trimmed) ?? PAIR.exec(trimmed);
  const tableId = found?.[1];
  const code = found?.[2];
  return tableId !== undefined && code !== undefined ? { tableId, code } : null;
}

/** O link de convite; o código vai no fragmento, que não chega ao servidor. */
export function inviteLink(origin: string, tableId: string, code: string): string {
  return `${origin}/#/entrar/${tableId}/${code}`;
}

/** `localhost` e afins não servem de endereço para quem entra por outro aparelho. */
export function isLocalOrigin(origin: string): boolean {
  try {
    const host = new URL(origin).hostname;
    return (
      host === 'localhost' ||
      host === '127.0.0.1' ||
      host === '[::1]' ||
      host.endsWith('.localhost')
    );
  } catch {
    return false;
  }
}

/** O endereço que o anfitrião digita (`192.168.0.5:8765` ou com `http://`) como origem, ou `null` se não serve. */
export function normalizeOrigin(text: string): string | null {
  const trimmed = text.trim();
  if (trimmed === '') {
    return null;
  }
  try {
    const url = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`);
    return (url.protocol === 'http:' || url.protocol === 'https:') && url.hostname !== ''
      ? url.origin
      : null;
  } catch {
    return null;
  }
}
