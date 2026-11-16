import { defineConfig } from 'vitest/config';

// Testes de ferramenta (lint, tokens): rodam em Node, fora do builder do Angular, porque leem arquivos
// e usam a API do ESLint.
export default defineConfig({
  test: { globals: true, environment: 'node', include: ['tools/**/*.spec.ts'] },
});
