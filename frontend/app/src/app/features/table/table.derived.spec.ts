import type { Character, TableView } from '@contract/api_responses';
import { ACT_BLOCK_TEXT } from '@shared/game/rules';
import { campaignView, rulesView, tableView } from '../../testing/fixtures';
import { blockedReasonOf, characterOf, sceneFor, targetsOf } from './table.derived';

const bia: Character = { id: 'bia', name: 'Bia', attributes: {}, hp: 8, max_hp: 10, inventory: [] };

function mesa(over: Partial<TableView> = {}): TableView {
  const view = tableView({
    players: [{ id: 'p2', name: 'Bia', role: 'player', character_ids: ['bia'] }],
    ...over,
  });
  view.state = { ...view.state, turn: 2, characters: { bia } };
  return view;
}

describe('characterOf', () => {
  it('é o primeiro personagem de quem olha', () => {
    expect(characterOf(mesa())?.name).toBe('Bia');
  });
  it('é null sem mesa ou sem personagem criado', () => {
    expect(characterOf(null)).toBeNull();
    expect(characterOf(tableView())).toBeNull();
  });
});

describe('sceneFor', () => {
  it('é null até haver mesa e campanha', () => {
    expect(sceneFor(null, campaignView())).toBeNull();
    expect(sceneFor(mesa(), null)).toBeNull();
  });
  it('mostra o local e as saídas que o servidor entregou ao jogador', () => {
    const scene = sceneFor(mesa(), campaignView());
    expect(scene?.name).toBe('Vila');
    expect(scene?.exits.map((e) => e.id)).toEqual(['floresta']);
  });
});

describe('blockedReasonOf', () => {
  it('vazio quando o personagem pode agir ou ainda não há dados', () => {
    expect(blockedReasonOf(mesa(), rulesView(), bia)).toBe('');
    expect(blockedReasonOf(null, rulesView(), bia)).toBe('');
    expect(blockedReasonOf(mesa(), null, bia)).toBe('');
  });
  it('diz o motivo quando já agiu neste turno', () => {
    expect(blockedReasonOf(mesa({ acted: { bia: 2 } }), rulesView(), bia)).toBe(
      ACT_BLOCK_TEXT['acted'],
    );
  });
  it('diz o motivo quando a partida acabou', () => {
    expect(blockedReasonOf(mesa({ status: 'won' }), rulesView(), bia)).toBe(ACT_BLOCK_TEXT['over']);
  });
});

describe('targetsOf', () => {
  it('é vazio sem mesa ou sem cena', () => {
    expect(targetsOf(null, null)).toEqual([]);
    expect(targetsOf(mesa(), null)).toEqual([]);
  });
  it('lista os NPCs da cena com o hp que o estado traz', () => {
    const view = mesa();
    view.state = {
      ...view.state,
      npcs: { ferreiro: { alive: true, hp: 4, max_hp: 5, hostile: false } } as never,
    };
    const scene = sceneFor(view, campaignView());
    const targets = targetsOf(view, scene);
    expect(targets.map((t) => [t.id, t.hp, t.maxHp])).toEqual([['ferreiro', 4, 5]]);
  });
});
