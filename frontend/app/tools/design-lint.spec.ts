import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  definedTokens,
  inlineStyles,
  lintCss,
  undefinedTokens,
  unreadableStyles,
} from './design-lint';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = join(root, 'src');

function walk(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? walk(join(dir, entry.name)) : [join(dir, entry.name)],
  );
}

describe('a regra de ouro, provada em CSS de exemplo', () => {
  const lint = (css: string, file = 'x.css'): string[] => lintCss(css, file);

  it.each([
    ['cor em hex', '.a { color: #fff; }'],
    ['cor oklch fora dos tokens', '.a { color: oklch(50% 0.1 20); }'],
    ['cor rgb', '.a { color: rgb(0 0 0); }'],
    ['duração literal', '.a { animation: x 0.5s; }'],
    ['duração em ms', '.a { transition: color 140ms; }'],
    ['curva literal', '.a { transition-timing-function: ease-out; }'],
    ['curva cubic-bezier', '.a { animation-timing-function: cubic-bezier(0, 0, 1, 1); }'],
    ['z-index literal', '.a { z-index: 5; }'],
    ['sombra literal', '.a { box-shadow: 0 1px 2px black; }'],
    ['px literal', '.a { padding: 12px; }'],
    ['!important', '.a { color: red !important; }'],
    ['cor nomeada', '.a { color: red; }'],
    ['fundo nomeado', '.a { background: black; }'],
    ['transition all', '.a { transition: all var(--dv-duration-fast); }'],
    ['animação infinita', '.a { animation: x var(--dv-duration-base) infinite; }'],
    ['rolagem animada', 'html { scroll-behavior: smooth; }'],
    ['anima largura', '.a { transition: width var(--dv-duration-base); }'],
    ['anima altura em keyframes', '@keyframes k { from { height: 0; } }'],
  ])('barra %s', (_nome, css) => {
    expect(lint(css)).not.toEqual([]);
  });

  it.each([
    ['uma cor por token', '.a { color: var(--dv-text); }'],
    [
      'transição de cor com tokens',
      '.a { transition: color var(--dv-duration-fast) var(--dv-ease-standard); }',
    ],
    [
      'animação de opacidade e transform',
      '@keyframes k { from { opacity: 0; transform: translateY(1rem); } }',
    ],
    ['z-index por token', '.a { z-index: var(--dv-z-sticky); }'],
    ['sombra por token', '.a { box-shadow: var(--dv-shadow-float); }'],
    ['rem', '.a { padding: 0.75rem; }'],
    ['cor transparente e herdada', '.a { color: inherit; background: transparent; }'],
    [
      'animação finita com iterações por token',
      '.a { animation: x var(--dv-duration-base) var(--dv-iterations-pending); }',
    ],
    ['cor dentro de comentário', '/* #fff e 0.5s */ .a { color: var(--dv-text); }'],
  ])('aceita %s', (_nome, css) => {
    expect(lint(css)).toEqual([]);
  });

  it('em tokens.css vale tudo, menos !important e animar layout', () => {
    expect(
      lintCss(':root { --x: oklch(50% 0.1 20); --d: 0.5s; }', 'tokens.css', { isTokens: true }),
    ).toEqual([]);
    expect(lintCss(':root { --x: red !important; }', 'tokens.css', { isTokens: true })).not.toEqual(
      [],
    );
  });

  it.each([
    ['aspas simples', "@Component({ styles: ':host { color: #fff; }' })"],
    ['aspas duplas', '@Component({ styles: ["a { color: #fff; }"] })'],
    ['crase', '@Component({ styles: `a { color: #fff; }` })'],
    [
      'lista com vários itens',
      "@Component({ styles: [':host { display: block; }', 'a { color: #fff; }'] })",
    ],
  ])('acha o CSS inline de um componente (%s)', (_forma, source) => {
    expect(inlineStyles(source)).toContain('#fff');
  });

  it('sem styles, nada; com interpolação, reprova', () => {
    expect(inlineStyles('@Component({ template: `x` })')).toBe('');
    expect(unreadableStyles('@Component({ styles: `a { color: ${cor}; }` })')).toBe(true);
    expect(unreadableStyles("@Component({ styles: 'a { }' })")).toBe(false);
  });

  it('acusa token inexistente', () => {
    const defined = definedTokens(':root { --dv-text: red; }');
    expect(undefinedTokens('.a { color: var(--dv-nada); }', defined, 'x.css')).toHaveLength(1);
    expect(undefinedTokens('.a { color: var(--dv-text); }', defined, 'x.css')).toEqual([]);
  });
});

const source0 = (file: string): string => readFileSync(file, 'utf-8');

/** Tokens declarados para os PRs de componentes e de telas, ainda sem consumidor: a lista só pode encolher. */
const WAITING = ['--dv-space-8', '--dv-z-overlay'];

describe('o estilo do app só consome tokens', () => {
  const tokensCss = readFileSync(join(src, 'styles/tokens.css'), 'utf-8');
  const defined = definedTokens(tokensCss);
  const files = walk(src).filter(
    (f) =>
      (f.endsWith('.css') || (f.endsWith('.ts') && !f.endsWith('.spec.ts'))) &&
      !f.includes('/testing/'),
  );

  it('tokens.css: sem !important nem animação de layout', () => {
    expect(lintCss(tokensCss, 'tokens.css', { isTokens: true })).toEqual([]);
  });

  it('todo CSS e todo `styles:` inline cumprem a regra', () => {
    expect(files.filter((f) => f.endsWith('.css')).length).toBeGreaterThan(15); // a varredura achou os arquivos
    const problems: string[] = [];
    for (const file of files) {
      const name = relative(root, file);
      if (file.endsWith('tokens.css')) {
        problems.push(...undefinedTokens(source0(file), defined, name));
        continue;
      }
      const source = readFileSync(file, 'utf-8');
      const css = file.endsWith('.css') ? source : inlineStyles(source);
      if (css === '') {
        continue;
      }
      problems.push(...lintCss(css, name), ...undefinedTokens(css, defined, name));
    }
    expect(problems).toEqual([]);
  });

  it('nenhum `styles:` inline usa interpolação (o lint não a lê)', () => {
    const offenders = files
      .filter((f) => f.endsWith('.ts'))
      .filter((f) => unreadableStyles(readFileSync(f, 'utf-8')))
      .map((f) => relative(root, f));
    expect(offenders).toEqual([]);
  });

  // Lacuna conhecida: só vê `style="..."` com aspas duplas e só hex, px e duração; `[style.color]` e `[ngStyle]` não.
  it('o `template` com `style=` solto não escapa dos tokens', () => {
    const offenders = walk(src)
      .filter((f) => /\.(html|ts)$/.test(f) && !f.endsWith('.spec.ts'))
      .filter((f) =>
        /\sstyle="[^"]*(?:#[0-9a-f]{3,8}|\d+px|\d+m?s)/i.test(readFileSync(f, 'utf-8')),
      )
      .map((f) => relative(root, f));
    expect(offenders).toEqual([]);
  });
});

describe('tokens sem uso', () => {
  const tokensCss = readFileSync(join(src, 'styles/tokens.css'), 'utf-8');
  const usedIn = walk(src)
    .filter(
      (f) => /\.(css|ts|html)$/.test(f) && !f.endsWith('.spec.ts') && !f.endsWith('.stories.ts'),
    )
    .map((f) => readFileSync(f, 'utf-8'))
    .join('\n');
  const unused = [...definedTokens(tokensCss)].filter((t) => !usedIn.includes(`var(${t}`));

  it('todo token tem consumidor, ou está na lista de espera', () => {
    expect(unused.filter((t) => !WAITING.includes(t))).toEqual([]);
  });

  it('a lista de espera só tem token que ainda não é usado (ela encolhe)', () => {
    expect(WAITING.filter((t) => !unused.includes(t))).toEqual([]);
  });
});
