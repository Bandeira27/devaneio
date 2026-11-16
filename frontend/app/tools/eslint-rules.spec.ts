import { readdirSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ESLint } from 'eslint';
import { FEATURES } from '../eslint.config.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const eslint = new ESLint({ cwd: root });

async function rules(code: string, filePath: string): Promise<string[]> {
  const [result] = await eslint.lintText(code, { filePath: join(root, filePath) });
  return (result?.messages ?? []).map((m) => `${m.ruleId}: ${m.message}`);
}

// Montadas aqui para este arquivo não conter a diretiva literal (scripts/check_suppressions.py a barra).
const directive = (name: string): string => '// @' + 'ts-' + name;

async function ruleIds(code: string, filePath: string): Promise<string[]> {
  return (await rules(code, filePath)).map((m) => m.split(':')[0] ?? '');
}

describe('camadas do app', () => {
  it('core não importa shared, features nem layout', async () => {
    for (const from of ['@shared/game/commands', '@features/home/x', '@layout/shell']) {
      expect(
        await ruleIds(`import { x } from '${from}';\nconsole.warn(x);\n`, 'src/app/core/api/a.ts'),
      ).toContain('no-restricted-imports');
    }
  });

  it('shared não importa core, features nem layout, e shared/game não usa o CDK', async () => {
    const file = 'src/app/shared/game/a.ts';
    for (const from of [
      '@core/api/client',
      '@features/home/x',
      '@layout/shell',
      '@angular/cdk/dialog',
    ]) {
      expect(await ruleIds(`import { x } from '${from}';\nconsole.warn(x);\n`, file)).toContain(
        'no-restricted-imports',
      );
    }
  });

  it('só shared/ui importa o CDK', async () => {
    const code = "import { Dialog } from '@angular/cdk/dialog';\nconsole.warn(Dialog);\n";
    expect(await ruleIds(code, 'src/app/shared/ui/sheet/a.ts')).not.toContain(
      'no-restricted-imports',
    );
    for (const where of [
      'src/app/features/home/a.ts',
      'src/app/layout/a.ts',
      'src/app/core/a.ts',
      'src/app/shared/util/a.ts',
    ]) {
      expect(await ruleIds(code, where)).toContain('no-restricted-imports');
    }
  });

  it('shared/ui também não importa core, features nem layout', async () => {
    expect(
      await ruleIds(
        "import { x } from '@core/api/client';\nconsole.warn(x);\n",
        'src/app/shared/ui/a.ts',
      ),
    ).toContain('no-restricted-imports');
  });

  it('feature não importa outra feature nem o layout, mas usa shared e core', async () => {
    const file = 'src/app/features/home/pages/a.ts';
    for (const from of ['@features/join/x', '../../../join/x', '@layout/shell']) {
      expect(await ruleIds(`import { x } from '${from}';\nconsole.warn(x);\n`, file)).toContain(
        'no-restricted-imports',
      );
    }
    for (const from of ['@shared/game/commands', '@core/api/client', '../components/card']) {
      expect(await ruleIds(`import { x } from '${from}';\nconsole.warn(x);\n`, file)).not.toContain(
        'no-restricted-imports',
      );
    }
  });

  it('layout usa shared e core, mas não features', async () => {
    const file = 'src/app/layout/a.ts';
    expect(
      await ruleIds("import { x } from '@features/home/x';\nconsole.warn(x);\n", file),
    ).toContain('no-restricted-imports');
    expect(
      await ruleIds("import { x } from '@shared/ui/x';\nconsole.warn(x);\n", file),
    ).not.toContain('no-restricted-imports');
  });

  it('os pacotes @angular/* nunca contam como camada (@angular/core/testing não é a pasta core)', async () => {
    const code = "import { TestBed } from '@angular/core/testing';\nconsole.warn(TestBed);\n";
    for (const where of [
      'src/app/shared/ui/a.spec.ts',
      'src/app/shared/game/a.ts',
      'src/app/features/table/a.ts',
      'src/app/layout/a.ts',
    ]) {
      expect(await ruleIds(code, where), where).not.toContain('no-restricted-imports');
    }
  });

  it('toda pasta de features está registrada na configuração', () => {
    const dir = join(root, 'src/app/features');
    const found = existsSync(dir)
      ? readdirSync(dir, { withFileTypes: true })
          .filter((e) => e.isDirectory())
          .map((e) => e.name)
      : [];
    expect(found.filter((name) => !FEATURES.includes(name))).toEqual([]);
  });
});

describe('segurança do front', () => {
  const file = 'src/app/features/home/a.ts';

  it.each([
    [
      'bypassSecurityTrustHtml',
      "declare const s: { bypassSecurityTrustHtml(v: string): string };\nconsole.warn(s.bypassSecurityTrustHtml('<b>'));\n",
    ],
    [
      'bypassSecurityTrustUrl',
      "declare const s: { bypassSecurityTrustUrl(v: string): string };\nconsole.warn(s.bypassSecurityTrustUrl('x'));\n",
    ],
    ['eval', "console.warn(eval('1'));\n"],
    ['new Function', "console.warn(new Function('return 1'));\n"],
    ['innerHTML', "declare const e: HTMLElement;\ne.innerHTML = '<b>x</b>';\n"],
    ['outerHTML', "declare const e: HTMLElement;\ne.outerHTML = '<b>x</b>';\n"],
    [
      'insertAdjacentHTML',
      "declare const e: HTMLElement;\ne.insertAdjacentHTML('beforeend', 'x');\n",
    ],
  ])('proíbe %s', async (_name, code) => {
    expect(await ruleIds(code, file)).toContain('no-restricted-syntax');
  });

  it('proíbe [innerHTML] nos templates', async () => {
    const found = await ruleIds(
      '<div [innerHTML]="texto"></div>\n',
      'src/app/features/home/a.html',
    );
    expect(found).toContain('no-restricted-syntax');
  });

  it('aceita interpolação', async () => {
    const found = await ruleIds('<p>{{ texto }}</p>\n', 'src/app/features/home/a.html');
    expect(found).not.toContain('no-restricted-syntax');
  });

  it('proíbe any explícito e a diretiva de ignorar tipo, e exige descrição na de esperar erro', async () => {
    expect(await ruleIds('export const a: any = 1;\n', file)).toContain(
      '@typescript-eslint/no-explicit-any',
    );
    expect(
      await ruleIds(`${directive('ignore')}\nexport const a: number = "x";\n`, file),
    ).toContain('@typescript-eslint/ban-ts-comment');
    expect(
      await ruleIds(`${directive('expect-error')}\nexport const a: number = "x";\n`, file),
    ).toContain('@typescript-eslint/ban-ts-comment');
  });

  it('o código sem violação passa limpo', async () => {
    expect(await rules('export const a = 1;\n', file)).toEqual([]);
  });
});

describe('acessibilidade dos templates', () => {
  const html = 'src/app/features/home/a.html';

  it('exige texto alternativo e conteúdo nos botões', async () => {
    const found = await ruleIds('<img src="a.png"><button></button>\n', html);
    expect(found).toContain('@angular-eslint/template/alt-text');
    expect(found).toContain('@angular-eslint/template/elements-content');
  });

  it('exige teclado em elemento clicável', async () => {
    const found = await ruleIds('<div (click)="x()">oi</div>\n', html);
    expect(found).toContain('@angular-eslint/template/click-events-have-key-events');
    expect(found).toContain('@angular-eslint/template/interactive-supports-focus');
  });
});

describe('documentação (JSDoc)', () => {
  const file = 'src/app/shared/game/a.ts';

  it('exige JSDoc no que o módulo exporta', async () => {
    expect(
      await ruleIds('export function soma(a: number): number {\n  return a;\n}\n', file),
    ).toContain('jsdoc/require-jsdoc');
    expect(await ruleIds('export interface Forma {\n  lado: number;\n}\n', file)).toContain(
      'jsdoc/require-jsdoc',
    );
  });

  it('aceita o exportado com JSDoc e o que não é exportado sem ele', async () => {
    const code =
      '/** Devolve o valor. */\nexport function soma(a: number): number {\n  return a;\n}\n';
    expect(await ruleIds(code, file)).not.toContain('jsdoc/require-jsdoc');
    expect(
      await ruleIds(
        'function interna(): number {\n  return 1;\n}\nconsole.warn(interna());\n',
        file,
      ),
    ).not.toContain('jsdoc/require-jsdoc');
  });

  it('proíbe tipo dentro do JSDoc (o TypeScript já os tem)', async () => {
    const code =
      '/**\n * Soma.\n * @param {number} a O valor.\n */\nexport function soma(a: number): number {\n  return a;\n}\n';
    expect(await ruleIds(code, file)).toContain('jsdoc/no-types');
  });

  it('não exige JSDoc em teste nem em montagem de teste', async () => {
    const code = 'export function ajuda(): number {\n  return 1;\n}\n';
    expect(await ruleIds(code, 'src/app/testing/a.ts')).not.toContain('jsdoc/require-jsdoc');
  });
});
