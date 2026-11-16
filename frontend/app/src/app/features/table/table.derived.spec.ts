import type { Character, TableView } from '@contract/api_responses';
import { ACT_BLOCK_TEXT } from '@shared/game/rules';
import { campaignView, rulesView, tableView } from '../../testing/fixtures';
import {
  blockedReasonOf,
  characterOf,
  connectionBlockOf,
  sceneFor,
  targetsOf,
  turnStatusOf,
} from './table.derived';

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

describe('connectionBlockOf', () => {
  it('só bloqueia quando a mesa não está ao vivo', () => {
    expect(connectionBlockOf('live')).toBe('');
    expect(connectionBlockOf('connecting')).toBe('');
    expect(connectionBlockOf('offline')).toContain('Tentando de novo');
    expect(connectionBlockOf('expired')).toContain('sessão');
    expect(connectionBlockOf('gone')).toContain('não existe mais');
    expect(connectionBlockOf('failed')).not.toBe('');
  });
});

describe('turnStatusOf', () => {
  const zed: Character = {
    id: 'zed',
    name: 'Zed',
    attributes: {},
    hp: 7,
    max_hp: 10,
    inventory: [],
  };
  const com = (over: Partial<TableView>): TableView => {
    const view = mesa(over);
    view.state = { ...view.state, characters: { bia, zed } };
    return view;
  };
  const rules = rulesView();

  it('sem mesa ou sem regras não diz nada', () => {
    expect(turnStatusOf(null, rules, bia)).toBe('');
    expect(turnStatusOf(com({}), null, bia)).toBe('');
  });

  it('partida encerrada e fora de combate vêm da mesma regra que bloqueia os botões', () => {
    expect(turnStatusOf(com({ status: 'won' }), rules, bia)).toBe('Partida encerrada');
    expect(turnStatusOf(com({}), rules, { ...bia, hp: 0 })).toBe('Você está fora de combate');
  });

  it('com a regra "caído age", quem está caído ainda tem a vez', () => {
    const livre = { ...rules, combat: { ...rules.combat, fallen_can_act: true } };
    expect(turnStatusOf(com({}), livre, { ...bia, hp: 0 })).toBe('Sua vez de agir');
  });

  it('sem personagem a tela já avisa: a linha fica vazia', () => {
    expect(turnStatusOf(com({}), rules, null)).toBe('');
  });

  it('é a sua vez enquanto você não agiu', () => {
    expect(turnStatusOf(com({}), rules, bia)).toBe('Sua vez de agir');
  });

  it('já agiu: diz quem falta (só quem está de pé e ainda não agiu)', () => {
    expect(turnStatusOf(com({ acted: { bia: 2 } }), rules, bia)).toBe('Você já agiu · falta Zed');
    expect(turnStatusOf(com({ acted: { bia: 2, zed: 2 } }), rules, bia)).toBe('Você já agiu');
  });
});
