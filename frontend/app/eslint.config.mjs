// Camadas, segurança e acessibilidade do app, impostas por lint (o equivalente do import-linter do
// backend). Desenho em docs/desenho-ui.md; a política de supressões vale aqui também
// (scripts/check_suppressions.py): todo comentário que desliga uma regra cita a regra e traz justificativa.
// @ts-check
import eslint from '@eslint/js';
import angular from 'angular-eslint';
import { defineConfig } from 'eslint/config';
import jsdoc from 'eslint-plugin-jsdoc';
import tseslint from 'typescript-eslint';

/** Features existentes: um teste (tools/eslint-rules.spec.ts) falha se uma pasta nova não estiver aqui. */
export const FEATURES = [
  'home',
  'campaign',
  'invite',
  'join',
  'character',
  'table',
  'editor',
  'settings',
];

const MESSAGE = {
  cdk: 'O CDK só entra por shared/ui (componentes dv-*): as features usam dv-*.',
  core: 'core não depende de shared, features nem layout, e vice-versa só features/layout usam core.',
};

const cdk = { group: ['@angular/cdk', '@angular/cdk/*'], message: MESSAGE.cdk };
const only = (layer, from, reason) => ({
  group: [`@${layer}/*`, `**/${layer}/**`, '!@angular/**'], // @angular/core/* não é a camada core
  message: `${from} não pode importar de ${layer}: ${reason}`,
});

const toCore = only('core', 'shared', 'shared e core não dependem um do outro');
const toShared = only('shared', 'core', 'shared e core não dependem um do outro');
const toFeatures = (from) =>
  only('features', from, 'features só são importadas pelas rotas do app');
const toLayout = (from) => only('layout', from, 'o shell não é dependência de ninguém');

const restrict = (...patterns) => ({
  'no-restricted-imports': ['error', { patterns }],
});

const SECURITY = [
  {
    selector: 'CallExpression[callee.property.name=/^bypassSecurityTrust/]',
    message:
      'bypassSecurityTrust* desliga a sanitização do Angular: tudo é texto (rule 05, item 24).',
  },
  { selector: "CallExpression[callee.name='eval']", message: 'Sem eval (rule 05, item 6).' },
  {
    selector: "NewExpression[callee.name='Function']",
    message: 'Sem new Function (rule 05, item 6).',
  },
  {
    selector: 'AssignmentExpression[left.property.name=/^(innerHTML|outerHTML)$/]',
    message: 'Sem innerHTML/outerHTML: o front trata todo texto como texto (rule 05, item 24).',
  },
  {
    selector: "CallExpression[callee.property.name='insertAdjacentHTML']",
    message: 'Sem insertAdjacentHTML: o front trata todo texto como texto (rule 05, item 24).',
  },
];

export default defineConfig([
  { ignores: ['dist/**', '.angular/**', 'coverage/**', 'node_modules/**', 'storybook-static/**'] },
  {
    files: ['**/*.ts'],
    extends: [
      eslint.configs.recommended,
      tseslint.configs.strict,
      tseslint.configs.stylistic,
      angular.configs.tsRecommended,
    ],
    processor: angular.processInlineTemplates,
    rules: {
      '@angular-eslint/component-selector': [
        'error',
        { type: 'element', prefix: 'dv', style: 'kebab-case' },
      ],
      '@angular-eslint/directive-selector': [
        'error',
        { type: 'attribute', prefix: 'dv', style: 'camelCase' },
      ],
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-extraneous-class': ['error', { allowWithDecorator: true }],
      '@typescript-eslint/ban-ts-comment': [
        'error',
        { 'ts-expect-error': 'allow-with-description', minimumDescriptionLength: 10 },
      ],
      eqeqeq: ['error', 'always'],
      'no-console': ['error', { allow: ['warn', 'error'] }],
      'no-restricted-syntax': ['error', ...SECURITY],
      ...restrict(cdk),
    },
  },
  // Camadas: cada pasta só enxerga o que o desenho permite.
  {
    files: ['src/app/core/**/*.ts'],
    rules: restrict(toShared, toFeatures('core'), toLayout('core'), cdk),
  },
  {
    files: ['src/app/shared/**/*.ts'],
    ignores: ['src/app/shared/ui/**'],
    rules: restrict(toCore, toFeatures('shared'), toLayout('shared'), cdk),
  },
  {
    files: ['src/app/shared/ui/**/*.ts'],
    rules: restrict(toCore, toFeatures('shared'), toLayout('shared')), // o CDK é permitido aqui
  },
  { files: ['src/app/layout/**/*.ts'], rules: restrict(toFeatures('layout'), cdk) },
  ...FEATURES.map((feature) => ({
    files: [`src/app/features/${feature}/**/*.ts`],
    rules: restrict(
      toLayout(`features/${feature}`),
      cdk,
      ...FEATURES.filter((other) => other !== feature).map((other) => ({
        group: [`@features/${other}`, `@features/${other}/*`, `**/${other}/**`, '!@angular/**'],
        message: `features/${feature} não importa features/${other}: o que as duas precisam sobe para shared.`,
      })),
    ),
  })),
  // Catálogo (rule 11): stories e a configuração do Storybook não são API do app: sem JSDoc obrigatório.
  {
    files: ['src/**/*.stories.ts', '.storybook/**/*.ts'],
    rules: {
      '@angular-eslint/component-selector': 'off',
      '@typescript-eslint/no-extraneous-class': 'off',
    },
  },
  // Documentação (rule 10): JSDoc sem tipos em tudo que o app exporta; `@param` só quando acrescenta algo.
  {
    files: ['src/app/**/*.ts'],
    ignores: ['**/*.spec.ts', '**/*.stories.ts', 'src/app/testing/**'],
    plugins: { jsdoc },
    rules: {
      'jsdoc/require-jsdoc': [
        'error',
        {
          publicOnly: true,
          require: { ClassDeclaration: true, FunctionDeclaration: true },
          contexts: ['TSInterfaceDeclaration', 'TSTypeAliasDeclaration'],
        },
      ],
      'jsdoc/check-tag-names': 'error',
      'jsdoc/check-param-names': 'error',
      'jsdoc/no-types': 'error',
      'jsdoc/check-alignment': 'error',
    },
  },
  {
    files: ['**/*.html'],
    extends: [angular.configs.templateRecommended, angular.configs.templateAccessibility],
    rules: {
      // [innerHTML] sanitiza, mas o desenho manda tudo como texto (rule 05, item 24).
      'no-restricted-syntax': [
        'error',
        {
          selector: "BoundAttribute[name='innerHTML']",
          message: 'Sem [innerHTML]: o front trata todo texto como texto (rule 05, item 24).',
        },
      ],
    },
  },
  {
    files: ['tools/**/*.ts', '*.mjs', '*.ts', '*.mts'],
    rules: { 'no-restricted-imports': 'off', 'no-restricted-syntax': 'off' },
  },
]);
