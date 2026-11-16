import { Component, type Type } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import type { StoryObj } from '@storybook/angular-vite';
import * as connectionBadge from '../features/table/components/connection-badge/connection-badge.stories';
import * as tokens from '../design/tokens.stories';
import * as motion from '../design/movimento.stories';
import * as button from '../shared/ui/button/button.stories';
import * as copyField from '../shared/ui/copy-field/copy-field.stories';
import * as field from '../shared/ui/field/field.stories';
import * as icon from '../shared/ui/icon/icon.stories';
import * as notice from '../shared/ui/notice/notice.stories';
import * as pips from '../shared/ui/pips/pips.stories';
import * as sheet from '../shared/ui/sheet/sheet.stories';
import * as stepper from '../shared/ui/stepper/stepper.stories';
import type { StoryRecipe } from './story';

/** Todos os arquivos de stories (tools/stories-list.spec.ts falha se um `*.stories.ts` novo não estiver aqui). */
const FILES: Record<string, Record<string, unknown>> = {
  'design/movimento.stories.ts': motion,
  'design/tokens.stories.ts': tokens,
  'features/table/components/connection-badge/connection-badge.stories.ts': connectionBadge,
  'shared/ui/button/button.stories.ts': button,
  'shared/ui/copy-field/copy-field.stories.ts': copyField,
  'shared/ui/field/field.stories.ts': field,
  'shared/ui/icon/icon.stories.ts': icon,
  'shared/ui/notice/notice.stories.ts': notice,
  'shared/ui/pips/pips.stories.ts': pips,
  'shared/ui/sheet/sheet.stories.ts': sheet,
  'shared/ui/stepper/stepper.stories.ts': stepper,
};

/** Um componente novo por receita: o template e os imports vêm da story, então o decorador é aplicado em tempo de execução (JIT). */
function hostOf(recipe: StoryRecipe): Type<unknown> {
  class StoryHost {
    readonly ready = true;
  }
  return Component({ template: recipe.template, imports: recipe.imports })(
    StoryHost,
  ) as Type<unknown>;
}

describe('catálogo de componentes (stories)', () => {
  const stories = Object.entries(FILES).flatMap(([file, module]) =>
    Object.entries(module)
      .filter(([name]) => name !== 'default')
      .map(([name, story]) => ({ id: `${file} › ${name}`, story: story as StoryObj })),
  );

  beforeEach(() => {
    // Elemento ou propriedade desconhecida (um `imports` esquecido, um componente renomeado) é erro, não aviso.
    TestBed.configureTestingModule({
      errorOnUnknownElements: true,
      errorOnUnknownProperties: true,
    });
  });

  it.each(stories)('renderiza $id sem erro e com conteúdo', async ({ story }) => {
    const recipe = (story.parameters as { dv?: StoryRecipe } | undefined)?.dv;
    expect(recipe, 'a story precisa ser feita com story() para poder ser testada').toBeDefined();
    const error = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    try {
      const fixture = TestBed.createComponent(hostOf(recipe as StoryRecipe));
      await fixture.whenStable();
      expect((fixture.nativeElement as HTMLElement).children.length).toBeGreaterThan(0);
      expect(error).not.toHaveBeenCalled();
    } finally {
      error.mockRestore();
    }
  });

  it('a folha aberta aparece no documento', async () => {
    const recipe = (sheet.Aberta.parameters as { dv: StoryRecipe }).dv;
    const fixture = TestBed.createComponent(hostOf(recipe));
    await fixture.whenStable();
    await Promise.resolve();
    expect(document.querySelector('.dv-sheet')).not.toBeNull();
    document.querySelectorAll('.cdk-overlay-container').forEach((el) => el.replaceChildren());
  });

  it('a página de tokens lista os tokens das folhas de estilo carregadas', async () => {
    const style = document.createElement('style');
    style.textContent = ':root { --dv-text: oklch(87.8% 0.045 90); --dv-space-1: 0.25rem; }';
    document.head.append(style);
    try {
      const recipe = (tokens.Todos.parameters as { dv: StoryRecipe }).dv;
      const fixture = TestBed.createComponent(hostOf(recipe));
      await fixture.whenStable();
      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelectorAll('.swatch').length).toBeGreaterThan(0);
      expect(el.textContent).toContain('--dv-space-1');
    } finally {
      style.remove();
    }
  });
});
