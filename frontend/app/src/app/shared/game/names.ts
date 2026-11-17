/** Nomes e ids de personagem: o que o jogador digita, limpo e conferido antes de virar uma linha de comando. */

/** O mesmo teto de tamanho por argumento que o servidor aplica ao `entrar` (`MAX_NAME`). */
export const MAX_ARG = 40;
const FORBIDDEN = /[\p{C}\p{Zl}\p{Zp}]/u;

/** NFKC e espaços colapsados, como o servidor faz com a linha. */
export function normalizeName(name: string): string {
  return name.normalize('NFKC').replace(/\s+/g, ' ').trim();
}

/** Mensagem em português se o nome não serve, ou `null`. */
export function validateName(name: string, empty = 'Dê um nome ao personagem.'): string | null {
  if (name.length === 0) {
    return empty;
  }
  if (name.length > MAX_ARG) {
    return `O nome pode ter até ${MAX_ARG} caracteres.`;
  }
  if (FORBIDDEN.test(name)) {
    return 'O nome não pode ter caracteres de controle ou invisíveis.';
  }
  return null;
}

/**
 * Id em slug a partir do nome: sem acento, minúsculas, `-` no lugar do resto, no máximo 24 caracteres. Sem nada
 * aproveitável no nome, devolve `fallback`.
 */
export function slugify(name: string, fallback = 'personagem'): string {
  const slug = name
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 24)
    .replace(/-+$/g, '');
  return slug === '' ? fallback : slug;
}

/** O slug, com `-2`, `-3`... se já estiver em uso (por outro personagem ou por um NPC). */
export function uniqueId(base: string, taken: Iterable<string>): string {
  const used = new Set(taken);
  if (!used.has(base)) {
    return base;
  }
  for (let n = 2; ; n++) {
    const candidate = `${base}-${n}`;
    if (!used.has(candidate)) {
      return candidate;
    }
  }
}
