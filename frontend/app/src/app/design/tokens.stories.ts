import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import type { Meta, StoryObj } from '@storybook/angular-vite';
import { story } from '../testing/story';

interface Token {
  name: string;
  value: string;
}

/** Os tokens `--dv-*` declarados em `:root`, lidos das folhas de estilo carregadas e resolvidos pelo navegador. */
function readTokens(): Token[] {
  const names = new Set<string>();
  for (const sheet of Array.from(document.styleSheets)) {
    let rules: CSSRuleList;
    try {
      rules = sheet.cssRules;
    } catch {
      continue; // folha de outra origem
    }
    for (const rule of Array.from(rules)) {
      if (rule instanceof CSSStyleRule && rule.selectorText === ':root') {
        for (const name of Array.from(rule.style)) {
          if (name.startsWith('--dv-')) {
            names.add(name);
          }
        }
      }
    }
  }
  const root = getComputedStyle(document.documentElement);
  return [...names].map((name) => ({ name, value: root.getPropertyValue(name).trim() }));
}

/** Catálogo dos tokens do tema: cores com amostra e o resto em lista. */
@Component({
  selector: 'dv-demo-tokens',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 class="dv-title">Cores</h2>
    <ul class="grid">
      @for (token of colors(); track token.name) {
        <li class="swatch">
          <span class="chip" [style.background]="'var(' + token.name + ')'"></span>
          <code>{{ token.name }}</code>
          <span class="dv-note">{{ token.value }}</span>
        </li>
      }
    </ul>
    <h2 class="dv-title">Outros</h2>
    <dl class="others">
      @for (token of others(); track token.name) {
        <dt>
          <code>{{ token.name }}</code>
        </dt>
        <dd>{{ token.value }}</dd>
      }
    </dl>
  `,
  styles: `
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
      gap: var(--dv-space-3);
      margin: var(--dv-space-4) 0;
      padding: 0;
      list-style: none;
    }
    .swatch {
      display: grid;
      gap: var(--dv-space-1);
    }
    .chip {
      display: block;
      height: var(--dv-touch);
      border: var(--dv-border-width) solid var(--dv-line);
      border-radius: var(--dv-radius);
    }
    .others {
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: var(--dv-space-1) var(--dv-space-4);
      margin: var(--dv-space-4) 0;
    }
    .others dd {
      margin: 0;
    }
  `,
})
class DemoTokens {
  private readonly tokens = signal(readTokens());
  protected readonly colors = () =>
    this.tokens().filter((t) => t.value.startsWith('oklch(') && !t.name.includes('shadow'));
  protected readonly others = () =>
    this.tokens().filter((t) => !(t.value.startsWith('oklch(') && !t.name.includes('shadow')));
}

const meta: Meta = { title: 'Design/Tokens' };
export default meta;

export const Todos: StoryObj = story([DemoTokens], '<dv-demo-tokens />');
