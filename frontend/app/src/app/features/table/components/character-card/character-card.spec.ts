import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { rulesView } from '../../../../testing/fixtures';
import { CharacterCard } from './character-card';

@Component({
  imports: [CharacterCard],
  template: `<dv-character-card [character]="character" [rules]="rules" />`,
})
class Host {
  readonly rules = rulesView();
  readonly character = {
    id: 'bia',
    name: 'Bia',
    attributes: { FOR: 3, AGI: 1 },
    hp: 6,
    max_hp: 10,
    inventory: ['punhos', 'item-sem-arma'],
  };
}

describe('CharacterCard', () => {
  it('mostra os atributos pelo nome, os pontos de vida e o inventário com o nome das armas', async () => {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const text = el.textContent as string;
    expect(text).toContain('Força');
    expect(el.querySelector('dv-key-value')?.textContent).toMatch(/Força\s*3/);
    expect(text).toContain('Punhos');
    expect(text).toContain('item-sem-arma'); // o que não é arma aparece como está
    expect(el.querySelector('dv-pips')?.getAttribute('aria-label')).toBe('pontos de vida: 6 de 10');
  });
});
