import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { definedTokens, inlineStyles, lintCss, undefinedTokens } from './design-lint';

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

  it('acha o CSS inline de um componente', () => {
    expect(inlineStyles("@Component({ styles: ':host { color: #fff; }' })")).toContain('#fff');
    expect(inlineStyles('@Component({ template: `x` })')).toBe('');
  });

  it('acusa token inexistente', () => {
    const defined = definedTokens(':root { --dv-text: red; }');
    expect(undefinedTokens('.a { color: var(--dv-nada); }', defined, 'x.css')).toHaveLength(1);
    expect(undefinedTokens('.a { color: var(--dv-text); }', defined, 'x.css')).toEqual([]);
  });
});

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
