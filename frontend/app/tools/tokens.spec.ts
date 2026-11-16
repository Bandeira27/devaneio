import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { contrast, oklchToSrgb, over, type Rgb } from './color';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const stylesDir = join(root, 'src/styles');
const tokens = readFileSync(join(stylesDir, 'tokens.css'), 'utf-8');

const MIN = 4.5; // WCAG AA para texto normal

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
  const parsed = /^oklch\(([\d.]+)%\s+([\d.]+)\s+([\d.]+)\)$/.exec(value(name));
  if (!parsed) {
    throw new Error(`${name} não é um oklch(L% C H): ${value(name)}`);
  }
  return oklchToSrgb(Number(parsed[1]) / 100, Number(parsed[2]), Number(parsed[3]));
}

const SURFACES = ['--dv-surface-0', '--dv-surface-1', '--dv-surface-2'];

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

  it.each(SURFACES)('o verdete e o tijolo (ok e erro) passam em %s', (surface) => {
    expect(contrast(color('--dv-ok'), color(surface))).toBeGreaterThanOrEqual(MIN);
    expect(contrast(color('--dv-danger'), color(surface))).toBeGreaterThanOrEqual(MIN);
  });

  it('o texto do botão de acento passa sobre o acento', () => {
    expect(contrast(color('--dv-on-accent'), color('--dv-accent'))).toBeGreaterThanOrEqual(MIN);
  });

  it.each(['--dv-surface-0', '--dv-surface-1'])(
    'o texto desbotado no piso de opacidade ainda passa em %s',
    (surface) => {
      const floor = Number(value('--dv-fade-floor'));
      const faded = over(color('--dv-text'), color(surface), floor);
      expect(contrast(faded, color(surface))).toBeGreaterThanOrEqual(MIN);
    },
  );

  it('um piso de opacidade menor reprovaria (o 0,55 da primeira ideia dava 4,2:1)', () => {
    const faded = over(color('--dv-text'), color('--dv-surface-0'), 0.55);
    expect(contrast(faded, color('--dv-surface-0'))).toBeLessThan(MIN);
  });
});

describe('arquivos de estilo', () => {
  const files = readdirSync(stylesDir).filter((name) => name.endsWith('.css'));

  it('não usam cor em hex, rgb nem hsl: só OKLCH', () => {
    for (const name of files) {
      const css = readFileSync(join(stylesDir, name), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '');
      expect(css, name).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
      expect(css, name).not.toMatch(/\b(?:rgb|rgba|hsl|hsla)\(/);
    }
  });

  it('o tema está todo em tokens: os componentes só usam var(--dv-...)', () => {
    const appDir = join(root, 'src/app');
    const walk = (dir: string): string[] =>
      readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
        entry.isDirectory() ? walk(join(dir, entry.name)) : [join(dir, entry.name)],
      );
    for (const file of walk(appDir).filter((f) => f.endsWith('.css'))) {
      const css = readFileSync(file, 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '');
      expect(css, file).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
      expect(css, file).not.toMatch(/\b(?:oklch|rgb|rgba|hsl|hsla)\(/);
    }
  });
});
