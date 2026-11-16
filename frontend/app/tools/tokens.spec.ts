import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { FADE_FLOOR } from '../src/app/shared/game/feed';
import { contrast, oklchToSrgb, over, type Rgb } from './color';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const stylesDir = join(root, 'src/styles');
const tokens = readFileSync(join(stylesDir, 'tokens.css'), 'utf-8');

const MIN = 4.5; // WCAG AA para texto normal
const NON_TEXT = 3; // WCAG 2.1 (1.4.11): componentes de interface e foco

/** Resolve `--dv-nome` até chegar num oklch(...) ou num número, seguindo `var(--dv-outro)`. */
function value(name: string, seen: string[] = []): string {
  if (seen.includes(name)) {
    throw new Error(`ciclo em ${name}`);
  }
  const match = new RegExp(`${name}:\\s*([^;]+);`).exec(tokens);
  if (!match?.[1]) {
    throw new Error(`token ${name} não existe`);
  }
  const raw = match[1].replace(/\/\*.*?\*\//g, '').trim();
  const ref = /^var\((--dv-[\w-]+)\)$/.exec(raw);
  return ref?.[1] ? value(ref[1], [...seen, name]) : raw;
}

function color(name: string): Rgb {
  const parsed = /^oklch\(([\d.]+)%\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*[\d.]+)?\)$/.exec(value(name));
  if (!parsed) {
    throw new Error(`${name} não é um oklch(L% C H): ${value(name)}`);
  }
  return oklchToSrgb(Number(parsed[1]) / 100, Number(parsed[2]), Number(parsed[3]));
}

const SURFACES = ['--dv-surface-0', '--dv-surface-1', '--dv-surface-2', '--dv-surface-3'];

describe('conversão de cor', () => {
  it('converte OKLCH para sRGB (a fumaça e a sépia do mockup)', () => {
    const [r, g, b] = oklchToSrgb(0.274, 0.01, 81).map((c) => Math.round(c * 255));
    expect([r, g, b]).toEqual([0x2a, 0x27, 0x22]);
    const sepia = oklchToSrgb(0.878, 0.045, 90).map((c) => Math.round(c * 255));
    expect(sepia).toEqual([0xe2, 0xd6, 0xb6]);
  });

  it('mede o contraste da WCAG (preto sobre branco é 21:1)', () => {
    expect(contrast([0, 0, 0], [1, 1, 1])).toBeCloseTo(21, 5);
    expect(contrast([1, 1, 1], [1, 1, 1])).toBeCloseTo(1, 5);
  });
});

/** O texto de leitura e as cores de papel que o feed desbota; cada uma com o seu piso (`--dv-fade-floor-*`). */
const FADED = {
  text: ['--dv-text'],
  quiet: ['--dv-text-muted', '--dv-accent', '--dv-ok', '--dv-danger'],
} as const;

describe('contraste dos tokens', () => {
  it.each(SURFACES)('o texto principal passa em %s', (surface) => {
    expect(contrast(color('--dv-text'), color(surface))).toBeGreaterThanOrEqual(MIN);
  });

  it.each(SURFACES)('a tinta velha (notas e rótulos) passa em %s', (surface) => {
    expect(contrast(color('--dv-text-muted'), color(surface))).toBeGreaterThanOrEqual(MIN);
  });

  it.each(SURFACES)('o rosa de poeira (acento, nome do falante) passa em %s', (surface) => {
    expect(contrast(color('--dv-accent'), color(surface))).toBeGreaterThanOrEqual(MIN);
  });

  it.each(SURFACES)('os tons de status (ok, aviso, informação, erro) passam em %s', (surface) => {
    for (const tone of ['--dv-ok', '--dv-warn', '--dv-info', '--dv-danger']) {
      expect(contrast(color(tone), color(surface)), tone).toBeGreaterThanOrEqual(MIN);
    }
  });

  it.each(['ok', 'warn', 'info', 'danger'])('o tom %s passa sobre o fundo dele', (tone) => {
    expect(
      contrast(color(`--dv-${tone}`), color(`--dv-${tone}-surface`)),
      tone,
    ).toBeGreaterThanOrEqual(MIN);
  });

  it('o texto do botão de acento passa sobre o acento, com o mouse e pressionado', () => {
    for (const state of ['--dv-accent', '--dv-accent-hover', '--dv-accent-pressed']) {
      expect(contrast(color('--dv-on-accent'), color(state)), state).toBeGreaterThanOrEqual(MIN);
    }
  });

  it('o texto selecionado passa sobre a seleção', () => {
    expect(contrast(color('--dv-text'), color('--dv-selection'))).toBeGreaterThanOrEqual(MIN);
  });

  it.each(SURFACES)('o texto desabilitado ainda se lê (>= 3:1) em %s', (surface) => {
    expect(contrast(color('--dv-text-disabled'), color(surface))).toBeGreaterThanOrEqual(NON_TEXT);
  });

  it('o botão de acento desabilitado ainda se lê (>= 3:1)', () => {
    expect(
      contrast(color('--dv-on-accent-disabled'), color('--dv-accent-disabled')),
    ).toBeGreaterThanOrEqual(NON_TEXT);
  });

  it.each(SURFACES)('o contorno de controle e o anel de foco passam de 3:1 em %s', (surface) => {
    for (const name of ['--dv-border-control', '--dv-focus-ring']) {
      expect(contrast(color(name), color(surface)), name).toBeGreaterThanOrEqual(NON_TEXT);
    }
  });
});

describe('o desbotado, por papel', () => {
  // O feed fica sobre a superfície 0.
  it.each(FADED.text)('%s ainda passa no piso do texto de leitura', (token) => {
    const floor = Number(value('--dv-fade-floor-text'));
    const faded = over(color(token), color('--dv-surface-0'), floor);
    expect(contrast(faded, color('--dv-surface-0'))).toBeGreaterThanOrEqual(MIN);
  });

  it.each(FADED.quiet)('%s ainda passa no piso das cores de papel', (token) => {
    const floor = Number(value('--dv-fade-floor-quiet'));
    const faded = over(color(token), color('--dv-surface-0'), floor);
    expect(contrast(faded, color('--dv-surface-0'))).toBeGreaterThanOrEqual(MIN);
  });

  it.each(FADED.quiet)('%s não passaria no piso do texto: por isso o piso maior', (token) => {
    const floor = Number(value('--dv-fade-floor-text'));
    const faded = over(color(token), color('--dv-surface-0'), floor);
    expect(contrast(faded, color('--dv-surface-0'))).toBeLessThan(MIN);
  });

  it('o piso do texto é o mesmo no CSS e no feed', () => {
    expect(Number(value('--dv-fade-floor-text'))).toBe(FADE_FLOOR);
  });
});
