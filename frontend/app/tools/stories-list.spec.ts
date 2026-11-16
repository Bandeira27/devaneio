import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const appDir = join(root, 'src/app');

function stories(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory()
      ? stories(join(dir, entry.name))
      : entry.name.endsWith('.stories.ts')
        ? [relative(appDir, join(dir, entry.name))]
        : [],
  );
}

describe('catálogo de componentes', () => {
  it('todo arquivo de stories entra no teste de fumaça (src/app/testing/stories.spec.ts)', () => {
    const spec = readFileSync(join(appDir, 'testing/stories.spec.ts'), 'utf-8');
    const missing = stories(appDir).filter((file) => !spec.includes(`'${file}'`));
    expect(missing).toEqual([]);
  });

  it('há stories (a varredura achou os arquivos)', () => {
    expect(stories(appDir).length).toBeGreaterThan(5);
  });
});
