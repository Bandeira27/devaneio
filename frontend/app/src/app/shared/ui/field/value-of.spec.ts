import { valueOf } from './value-of';

describe('valueOf', () => {
  it.each([
    ['input', () => document.createElement('input')],
    ['textarea', () => document.createElement('textarea')],
  ])('lê o texto de um %s', (_name, make) => {
    const field = make();
    document.body.append(field);
    field.value = 'olá';
    let seen = '';
    field.addEventListener('input', (event) => (seen = valueOf(event)));
    field.dispatchEvent(new Event('input'));
    field.remove();
    expect(seen).toBe('olá');
  });

  it('lê a opção escolhida de um select', () => {
    const select = document.createElement('select');
    select.add(new Option('Um', 'um'));
    select.add(new Option('Dois', 'dois'));
    select.value = 'dois';
    let seen = '';
    select.addEventListener('change', (event) => (seen = valueOf(event)));
    select.dispatchEvent(new Event('change'));
    expect(seen).toBe('dois');
  });
});
