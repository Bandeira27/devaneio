import type { Type } from '@angular/core';
import { moduleMetadata, type StoryObj } from '@storybook/angular-vite';

/** Os dados de uma story que o teste de fumaça usa para renderizá-la sem o Storybook. */
export interface StoryRecipe {
  imports: Type<unknown>[];
  template: string;
}

/**
 * Uma story feita de um template e dos componentes que ele usa. Guarda a receita em `parameters.dv`, para que
 * `stories.spec.ts` renderize todas no Vitest e a story não apodreça sem ninguém ver.
 */
export function story(imports: Type<unknown>[], template: string): StoryObj {
  const recipe: StoryRecipe = { imports, template };
  return {
    decorators: [moduleMetadata({ imports })],
    render: () => ({ template }),
    parameters: { dv: recipe },
  };
}
