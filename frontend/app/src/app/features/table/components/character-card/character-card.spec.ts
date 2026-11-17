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
    const text = (fixture.nativeElement as HTMLElement).textContent as string;
    expect(text).toContain('Força');
    expect(text).toContain('3');
    expect(text).toContain('Punhos');
    expect(text).toContain('item-sem-arma'); // o que não é arma aparece como está
    expect((fixture.nativeElement as HTMLElement).querySelector('dv-pips')).not.toBeNull();
  });
});
