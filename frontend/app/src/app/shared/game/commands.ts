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

/** Um marco muda de estado à mão: `marco ativar|concluir|falhar <id>`. */
export type BeatAction = 'ativar' | 'concluir' | 'falhar';

/** A linha `marco <ação> <id>`. */
export function beat(action: BeatAction, beatId: string): string {
  return `marco ${action} ${token('marco', beatId)}`;
}

/** A linha `revelar <id do fato>`. */
export function reveal(factId: string): string {
  return `revelar ${token('fato', factId)}`;
}

/** O tamanho de uma linha de texto que o servidor aceita (comando, fala, pergunta ao copiloto): 500 caracteres. */
export const MAX_LINE = 500;

/** Limites só da tela (o motor não os impõe): a quantia de um dano ou cura à mão e o tamanho da fonte dele. */
export const MAX_AMOUNT = 99;

/** O tamanho máximo da fonte de um dano ou de uma cura ("a queda", "poção"). */
export const MAX_SOURCE = 60;

/** Os dois comandos de quantia do anfitrião. */
export type AmountVerb = 'ferir' | 'curar';

function amountLine(verb: AmountVerb, targetId: string, amount: number, source: string): string {
  if (!Number.isInteger(amount) || amount < 1 || amount > MAX_AMOUNT) {
    throw new CommandError(`quantia inválida: ${String(amount)}`);
  }
  const base = `${verb} ${token('alvo', targetId)} ${amount}`;
  const clean = source.trim();
  if (clean === '') {
    return base;
  }
  if ([...clean].some((ch) => ch.charCodeAt(0) < 32 || ch.charCodeAt(0) === 127)) {
    throw new CommandError('a fonte não pode ter quebra de linha nem caracteres de controle');
  }
  if (clean.length > MAX_SOURCE) {
    throw new CommandError(`a fonte passa de ${MAX_SOURCE} caracteres`);
  }
  return `${base} ${quote(clean)}`;
}

/** A linha `ferir <alvo> <quantia> ["fonte"]`. */
export function hurt(targetId: string, amount: number, source = ''): string {
  return amountLine('ferir', targetId, amount, source);
}

/** A linha `curar <alvo> <quantia> ["fonte"]`. */
export function heal(targetId: string, amount: number, source = ''): string {
  return amountLine('curar', targetId, amount, source);
}

/** A linha `fim`: encerra o turno. */
export const END_TURN = 'fim';

/** A linha `descansar`: cura o grupo e passa o turno. */
export const REST = 'descansar';
