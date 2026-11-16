import { Component, type Type } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import type { StoryObj } from '@storybook/angular-vite';
import * as connectionBadge from '../features/table/components/connection-badge/connection-badge.stories';
import * as tokens from '../design/tokens.stories';
import * as motion from '../design/movimento.stories';
import * as button from '../shared/ui/button/button.stories';
import * as copyField from '../shared/ui/copy-field/copy-field.stories';
import * as field from '../shared/ui/field/field.stories';
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
  'shared/ui/notice/notice.stories.ts': notice,
  'shared/ui/pips/pips.stories.ts': pips,
  'shared/ui/sheet/sheet.stories.ts': sheet,
  'shared/ui/stepper/stepper.stories.ts': stepper,
};

/** Host só para o teste: o template e os imports vêm da receita, então o decorador é aplicado em tempo de execução (JIT). */
class StoryHost {
  readonly ready = true;
}

function hostOf(recipe: StoryRecipe): Type<unknown> {
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

  it.each(stories)('renderiza $id sem erro e com conteúdo', async ({ story }) => {
    const recipe = (story.parameters as { dv?: StoryRecipe } | undefined)?.dv;
    expect(recipe, 'a story precisa ser feita com story() para poder ser testada').toBeDefined();
    const Host = hostOf(recipe as StoryRecipe);
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    expect(
      (fixture.nativeElement as HTMLElement).textContent?.trim() ||
        fixture.nativeElement.querySelector('*'),
    ).toBeTruthy();
  });
});
