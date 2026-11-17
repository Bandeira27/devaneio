import { focusElement, isFocusFree } from './focus';

describe('foco', () => {
  let region: HTMLElement;
  let input: HTMLInputElement;
  let outside: HTMLButtonElement;

  beforeEach(() => {
    region = document.createElement('main');
    input = document.createElement('input');
    outside = document.createElement('button');
    region.append(input);
    document.body.append(region, outside);
  });

  afterEach(() => {
    region.remove();
    outside.remove();
  });

  it('livre quando nada está focado, ou só o body', () => {
    (document.activeElement as HTMLElement | null)?.blur();
    expect(isFocusFree()).toBe(true);
  });

  it('com um campo focado, não está livre; com `within`, só o que está fora da região ou nela mesma conta como livre', () => {
    input.focus();
    expect(isFocusFree()).toBe(false);
    expect(isFocusFree(region)).toBe(false); // quem digita dentro da região não perde o foco
    outside.focus();
    expect(isFocusFree(region)).toBe(true); // o foco está fora da região
    region.tabIndex = -1;
    region.focus();
    expect(isFocusFree(region)).toBe(true); // a própria região não é um campo
  });

  it('um elemento que saiu da tela não segura o foco', () => {
    input.focus();
    input.remove();
    expect(isFocusFree()).toBe(true);
  });

  it('focusElement foca um título sem rolar e o torna focável por programa', () => {
    const heading = document.createElement('h1');
    region.append(heading);
    focusElement(heading);
    expect(document.activeElement).toBe(heading);
    expect(heading.tabIndex).toBe(-1);
  });
});
