/**
 * Monta as linhas de comando que o servidor entende (`game/commands/`): o cliente só formata, quem decide
 * é o motor. Todo id vem de dado do servidor, mas vira texto de uma linha de comando: por isso cada pedaço
 * passa por uma checagem de formato antes (um id com espaço ou aspas viraria outro comando).
 */

export class CommandError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CommandError';
  }
}

/** O mesmo teto de tamanho por argumento que o servidor aplica ao `entrar` (`MAX_NAME`). */
export const MAX_ARG = 40;
const TOKEN = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
const ATTRIBUTE = /^[A-Z][A-Z0-9_]*$/;
const FORBIDDEN = /[\p{C}\p{Zl}\p{Zp}]/u;

function token(label: string, value: string): string {
  if (!TOKEN.test(value) || value.length > MAX_ARG) {
    throw new CommandError(`${label} inválido: "${value}"`);
  }
  return value;
}

/** Aspas duplas com `\` e `"` escapados: é o que o `shlex` do servidor desfaz. */
export function quote(text: string): string {
  return `"${text.replaceAll('\\', '\\\\').replaceAll('"', '\\"')}"`;
}

export function go(locationId: string): string {
  return `ir ${token('local', locationId)}`;
}

export function check(skillId: string, difficultyId: string, modifierId?: string | null): string {
  const base = `testar ${token('habilidade', skillId)} ${token('dificuldade', difficultyId)}`;
  return modifierId ? `${base} ${token('modificador', modifierId)}` : base;
}

export function attack(weaponId: string, targetId: string, modifierId?: string | null): string {
  const base = `atacar ${token('arma', weaponId)} ${token('alvo', targetId)}`;
  return modifierId ? `${base} ${token('modificador', modifierId)}` : base;
}

export function join(
  characterId: string,
  name: string,
  attributes: Readonly<Record<string, number>>,
): string {
  const clean = normalizeName(name);
  const error = validateName(clean);
  if (error !== null) {
    throw new CommandError(error);
  }
  const pairs = Object.entries(attributes).map(([key, value]) => {
    if (!ATTRIBUTE.test(key) || key.length > MAX_ARG || !Number.isInteger(value)) {
      throw new CommandError(`atributo inválido: ${key}=${String(value)}`);
    }
    return `${key}=${value}`;
  });
  return ['entrar', token('id', characterId), quote(clean), ...pairs].join(' ');
}

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

/** Id em slug a partir do nome: sem acento, minúsculas, `-` no lugar do resto, no máximo 24 caracteres. */
export function slugify(name: string): string {
  const slug = name
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 24)
    .replace(/-+$/g, '');
  return slug === '' ? 'personagem' : slug;
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
