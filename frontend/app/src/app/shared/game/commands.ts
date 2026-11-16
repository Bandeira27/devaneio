import { MAX_ARG, normalizeName, validateName } from './names';

/**
 * Monta as linhas de comando que o servidor entende (`game/commands/`): o cliente só formata, quem decide
 * é o motor. Todo id vem de dado do servidor, mas vira texto de uma linha de comando: por isso cada pedaço
 * passa por uma checagem de formato antes (um id com espaço ou aspas viraria outro comando).
 */

/** Um argumento que não pode virar linha de comando (formato inválido ou grande demais). */
export class CommandError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CommandError';
  }
}

const TOKEN = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
const ATTRIBUTE = /^[A-Z][A-Z0-9_]*$/;

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

/** A linha `ir <local>`. */
export function go(locationId: string): string {
  return `ir ${token('local', locationId)}`;
}

/** A linha `testar <habilidade> <dificuldade> [modificador]`. */
export function check(skillId: string, difficultyId: string, modifierId?: string | null): string {
  const base = `testar ${token('habilidade', skillId)} ${token('dificuldade', difficultyId)}`;
  return modifierId ? `${base} ${token('modificador', modifierId)}` : base;
}

/** A linha `atacar <arma> <alvo> [modificador]`. */
export function attack(weaponId: string, targetId: string, modifierId?: string | null): string {
  const base = `atacar ${token('arma', weaponId)} ${token('alvo', targetId)}`;
  return modifierId ? `${base} ${token('modificador', modifierId)}` : base;
}

/** A linha `entrar <id> "<nome>" ATRIBUTO=valor ...`; nome e atributos são conferidos antes. */
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
