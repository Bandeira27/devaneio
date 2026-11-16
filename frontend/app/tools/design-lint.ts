/**
 * A regra de ouro do design system (rule 11): o estilo só consome tokens. Estas funções leem CSS (e o `styles:` de
 * componentes) e devolvem o que foge disso; `design-lint.spec.ts` as roda sobre o app inteiro.
 */

const COLOR_PROPERTIES =
  /^(?:color|background|background-color|(?:border(?:-(?:top|right|bottom|left))?-color)|outline-color|fill|stroke|caret-color|text-decoration-color)$/;
const SAFE_COLOR = /^(?:transparent|currentcolor|inherit|none|initial|unset)$/i;

const LAYOUT_PROPERTIES =
  /^(?:width|height|min-width|max-width|min-height|max-height|top|right|bottom|left|inset|margin|padding|border-width|gap|flex-basis|font-size)(?:-[a-z]+)*$/;

/** Exceções conhecidas e justificadas: técnica de esconder visualmente e sentinela de rolagem de 1 px. */
const ALLOWED_PX: readonly { file: RegExp; line: RegExp }[] = [
  { file: /styles\/base\.css$/, line: /^(?:width|height|margin):\s*-?1px;?$/ },
  { file: /feed-list\.css$/, line: /^height:\s*1px;?$/ },
];

export function stripComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, '');
}

/**
 * Extrai o CSS do `styles:` inline de um componente (string ou lista de strings, com aspas simples, duplas ou
 * crase). Interpolação (`${}`) não é lida: `lintStylesSource` a reprova.
 */
export function inlineStyles(source: string): string {
  const start = /\bstyles:\s*/.exec(source);
  if (!start) {
    return '';
  }
  const rest = source.slice(start.index + start[0].length);
  const end = rest.startsWith('[') ? rest.indexOf(']') : rest.search(/[,}]\s*(?:\n|$)/);
  const value = end < 0 ? rest : rest.slice(0, end + 1);
  return [...value.matchAll(/'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`([^`]*)`/g)]
    .map((m) => m[1] ?? m[2] ?? m[3] ?? '')
    .join('\n');
}

/** `styles:` que o lint não consegue ler (interpolação), para reprovar em vez de passar em branco. */
export function unreadableStyles(source: string): boolean {
  return /\bstyles:/.test(source) && /\bstyles:[^;]*\$\{/.test(source);
}

/** Declarações `propriedade: valor` de um bloco, uma por entrada. */
function declarations(css: string): { property: string; value: string }[] {
  return [...css.matchAll(/([a-z-]+)\s*:\s*([^;{}]+)(?=;|})/g)].map((m) => ({
    property: m[1] ?? '',
    value: (m[2] ?? '').trim(),
  }));
}

function keyframeBodies(css: string): string[] {
  const bodies: string[] = [];
  const re = /@keyframes\s+[\w-]+\s*\{/g;
  for (let match = re.exec(css); match !== null; match = re.exec(css)) {
    let depth = 1;
    let i = re.lastIndex;
    while (i < css.length && depth > 0) {
      depth += css[i] === '{' ? 1 : css[i] === '}' ? -1 : 0;
      i++;
    }
    bodies.push(css.slice(re.lastIndex, i - 1));
  }
  return bodies;
}

/** Tudo em `css` que viola a regra de ouro; `file` só serve para a mensagem e para as exceções. */
export function lintCss(css: string, file: string, { isTokens = false } = {}): string[] {
  const clean = stripComments(css);
  const problems: string[] = [];
  const flag = (what: string, found: string): number => problems.push(`${file}: ${what}: ${found}`);

  if (!isTokens) {
    for (const m of clean.matchAll(/#[0-9a-fA-F]{3,8}\b/g)) {
      flag('cor em hex (use um token)', m[0]);
    }
    for (const m of clean.matchAll(
      /\b(?:oklch|oklab|lch|lab|rgba?|hsla?|hwb|color-mix|color)\([^)]*\)/g,
    )) {
      flag('cor fora de tokens.css', m[0]);
    }
    for (const m of clean.matchAll(/(?<![\w-])(\d*\.?\d+m?s)(?![\w-])/g)) {
      flag('duração literal (use --dv-duration-*)', m[1] ?? '');
    }
    for (const m of clean.matchAll(
      /(?<![\w-])(ease-in-out|ease-in|ease-out|ease|linear|cubic-bezier\([^)]*\))(?![\w(-])/g,
    )) {
      flag('curva literal (use --dv-ease-*)', m[1] ?? '');
    }
    for (const d of declarations(clean)) {
      if (
        COLOR_PROPERTIES.test(d.property) &&
        !SAFE_COLOR.test(d.value) &&
        !/var\(/.test(d.value)
      ) {
        flag('cor nomeada ou literal (use um token)', `${d.property}: ${d.value}`);
      }
      if (d.property === 'scroll-behavior' && d.value === 'smooth') {
        flag('rolagem animada (respeitaria o movimento reduzido só com um token)', d.value);
      }
      if (d.property.startsWith('animation') && /\binfinite\b/.test(d.value)) {
        flag('animação infinita (use var(--dv-iterations-pending))', d.value);
      }
      if (d.property === 'z-index' && !d.value.startsWith('var(')) {
        flag('z-index literal (use --dv-z-*)', d.value);
      }
      if (/^(?:box|text)-shadow$/.test(d.property) && !/^(?:var\(|none)/.test(d.value)) {
        flag('sombra literal (use --dv-shadow-*)', d.value);
      }
    }
    for (const line of clean.split('\n').map((l) => l.trim())) {
      for (const m of line.matchAll(/(?<![\w-])-?\d*\.?\d+px\b/g)) {
        const allowed = ALLOWED_PX.some((a) => a.file.test(file) && a.line.test(line));
        if (!allowed) {
          flag('px literal (use rem ou um token)', `${m[0]} em "${line}"`);
        }
      }
    }
  }

  for (const m of clean.matchAll(/!important/g)) {
    flag('!important', m[0]);
  }

  // Só se anima o que não força layout: opacidade, transform e cor.
  const animated: string[] = [];
  for (const d of declarations(clean)) {
    if (d.property === 'transition-property') {
      animated.push(...d.value.split(',').map((p) => p.trim()));
    } else if (d.property === 'transition') {
      animated.push(...d.value.split(',').map((part) => part.trim().split(/\s+/)[0] ?? ''));
    }
  }
  for (const body of keyframeBodies(clean)) {
    animated.push(...declarations(body).map((d) => d.property));
  }
  for (const property of animated) {
    if (property === 'all') {
      flag('transition: all anima layout (liste as propriedades)', property);
    } else if (LAYOUT_PROPERTIES.test(property)) {
      flag('anima propriedade que força layout (use opacity/transform)', property);
    }
  }
  return problems;
}

/** Os `var(--dv-x)` que o CSS usa e que `tokens.css` não define. */
export function undefinedTokens(css: string, defined: ReadonlySet<string>, file: string): string[] {
  const used = new Set(
    [...stripComments(css).matchAll(/var\((--dv-[\w-]+)/g)].map((m) => m[1] ?? ''),
  );
  return [...used]
    .filter((name) => !defined.has(name))
    .map((n) => `${file}: token inexistente: ${n}`);
}

/** Os tokens que `tokens.css` define. */
export function definedTokens(tokensCss: string): Set<string> {
  return new Set(
    [...stripComments(tokensCss).matchAll(/(--dv-[\w-]+)\s*:/g)].map((m) => m[1] ?? ''),
  );
}
