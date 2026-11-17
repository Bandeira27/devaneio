import type {
  AttributeInfo,
  Character,
  NpcInfo,
  NpcView,
  RulesView,
} from '@contract/api_responses';
import {
  ACT_BLOCK_TEXT,
  ActContext,
  actBlock,
  attackTargets,
  attributeDefaults,
  canStep,
  clampAttribute,
  humanizeFormula,
  plainNote,
  usableWeapons,
} from './rules';

const FOR: AttributeInfo = {
  id: 'FOR',
  name: 'Força',
  description: '',
  min: 1,
  max: 5,
  default: 2,
};
const MEN: AttributeInfo = {
  id: 'MEN',
  name: 'Mente',
  description: '',
  min: 0,
  max: 3,
  default: 1,
};

function rules(
  over: Partial<RulesView['combat']> = {},
  weapons = ['punhos', 'adaga', 'espada'],
): RulesView {
  return {
    id: 'default',
    name: 'Padrão',
    description: '',
    attributes: [FOR, MEN],
    skills: [],
    difficulties: [],
    modifiers: [],
    weapons: weapons.map((id) => ({
      id,
      name: id,
      description: '',
      skill: 'lutar',
      damage: '1d6',
    })),
    combat: { default_weapon: 'punhos', fallen_can_act: false, ...over },
  };
}

function character(over: Partial<Character> = {}): Character {
  return { id: 'aria', name: 'Aria', attributes: {}, hp: 10, max_hp: 10, inventory: [], ...over };
}

describe('atributos', () => {
  it('começa no padrão de cada atributo do sistema', () => {
    expect(attributeDefaults(rules())).toEqual({ FOR: 2, MEN: 1 });
  });

  it('prende o valor entre o mínimo e o máximo e arredonda', () => {
    expect(clampAttribute(FOR, 0)).toBe(1);
    expect(clampAttribute(FOR, 9)).toBe(5);
    expect(clampAttribute(FOR, 3.4)).toBe(3);
    expect(clampAttribute(MEN, -2)).toBe(0);
  });

  it('só deixa subir até o máximo e descer até o mínimo', () => {
    expect(canStep(FOR, 5, 1)).toBe(false);
    expect(canStep(FOR, 4, 1)).toBe(true);
    expect(canStep(FOR, 1, -1)).toBe(false);
    expect(canStep(FOR, 2, -1)).toBe(true);
  });
});

describe('armas', () => {
  it('a arma padrão vem primeiro, mesmo fora do inventário, e depois as do inventário', () => {
    const ids = usableWeapons(rules(), ['espada', 'tocha']).map((w) => w.id);
    expect(ids).toEqual(['punhos', 'espada']);
  });

  it('sem arma padrão só entra o que está no inventário', () => {
    expect(usableWeapons(rules({ default_weapon: null }), ['adaga']).map((w) => w.id)).toEqual([
      'adaga',
    ]);
    expect(usableWeapons(rules({ default_weapon: null }), [])).toEqual([]);
  });

  it('a arma padrão no inventário não aparece duas vezes', () => {
    expect(usableWeapons(rules(), ['punhos', 'adaga']).map((w) => w.id)).toEqual([
      'punhos',
      'adaga',
    ]);
  });

  it('uma arma padrão que o sistema não tem é ignorada', () => {
    expect(usableWeapons(rules({ default_weapon: 'garras' }), ['adaga']).map((w) => w.id)).toEqual([
      'adaga',
    ]);
  });
});

describe('quem pode agir', () => {
  const base: ActContext = {
    character: character(),
    turn: 3,
    acted: {},
    status: 'active',
    rules: rules(),
  };

  it('pode agir quando está de pé, não agiu e a partida segue', () => {
    expect(actBlock(base)).toBeNull();
  });

  it('sem personagem não age', () => {
    expect(actBlock({ ...base, character: null })).toBe('no-character');
  });

  it('partida encerrada trava (vitória e derrota)', () => {
    expect(actBlock({ ...base, status: 'won' })).toBe('over');
    expect(actBlock({ ...base, status: 'lost' })).toBe('over');
  });

  it('já agiu neste turno, mas não nos anteriores', () => {
    expect(actBlock({ ...base, acted: { aria: 3 } })).toBe('acted');
    expect(actBlock({ ...base, acted: { aria: 2 } })).toBeNull();
    expect(actBlock({ ...base, acted: { zed: 3 } })).toBeNull();
  });

  it('caído não age, a menos que o sistema deixe', () => {
    const fallen = character({ hp: 0 });
    expect(actBlock({ ...base, character: fallen })).toBe('fallen');
    expect(
      actBlock({ ...base, character: fallen, rules: rules({ fallen_can_act: true }) }),
    ).toBeNull();
  });

  it('a partida encerrada vem antes do resto', () => {
    expect(
      actBlock({ ...base, status: 'lost', acted: { aria: 3 }, character: character({ hp: 0 }) }),
    ).toBe('over');
  });

  it('todo motivo tem texto em português', () => {
    for (const reason of ['no-character', 'over', 'acted', 'fallen'] as const) {
      expect(ACT_BLOCK_TEXT[reason].length).toBeGreaterThan(5);
    }
  });
});

describe('alvos de ataque', () => {
  const present: NpcInfo[] = [
    { id: 'bram', name: 'Bram' },
    { id: 'vael', name: 'Irmão Vael' },
    { id: 'rato', name: 'Rato' },
  ];
  const state: Record<string, NpcView> = {
    bram: { alive: true, hp: 10, max_hp: 10, hostile: false },
    vael: { alive: true, hp: 4, max_hp: 12, hostile: true },
    rato: { alive: false, hp: 0, max_hp: 3, hostile: true },
  };

  it('lista só os NPCs presentes e de pé, com hp e hostilidade', () => {
    expect(attackTargets(present, state)).toEqual([
      { id: 'bram', name: 'Bram', hp: 10, maxHp: 10, hostile: false },
      { id: 'vael', name: 'Irmão Vael', hp: 4, maxHp: 12, hostile: true },
    ]);
  });

  it('um NPC presente sem estado visível não vira alvo', () => {
    expect(attackTargets([{ id: 'x', name: 'X' }], {})).toEqual([]);
  });

  it('hp zero com alive verdadeiro também não é alvo', () => {
    expect(
      attackTargets(present, {
        ...state,
        bram: { alive: true, hp: 0, max_hp: 10, hostile: false },
      }).map((t) => t.id),
    ).toEqual(['vael']);
  });
});

describe('humanizeFormula', () => {
  const attributes = [
    { id: 'FOR', name: 'Força' },
    { id: 'AGI', name: 'Agilidade' },
  ];

  it('troca o código do atributo pelo nome e deixa dados e números', () => {
    expect(humanizeFormula('2d6 + FOR', attributes)).toBe('2d6 + Força');
    expect(humanizeFormula('1d20 + AGI + 2', attributes)).toBe('1d20 + Agilidade + 2');
  });

  it('palavra que não é atributo fica como está', () => {
    expect(humanizeFormula('2d6 + XYZ', attributes)).toBe('2d6 + XYZ');
  });
});

describe('plainNote', () => {
  const attributes = [
    { id: 'FOR', name: 'Força' },
    { id: 'AGI', name: 'Agilidade' },
  ];

  it('atributos pelo nome, dados em palavras e "hp" como vida', () => {
    expect(
      plainNote('Ana testa Lutar (2d6 + FOR): 2d6 [3, 4] → total 11, sucesso', attributes),
    ).toBe('Ana testa Lutar (2d6 + Força): 2d6: 3 e 4, total 11, sucesso');
    expect(plainNote('Ana entra na aventura (FOR 3, AGI 2; hp 8).', attributes)).toBe(
      'Ana entra na aventura (Força 3, Agilidade 2; vida 8).',
    );
  });

  it('a seta de uma mudança vira "para"; um dado só e três dados também leem bem', () => {
    expect(plainNote('Ana cura: hp 3 → 7', attributes)).toBe('Ana cura: vida 3 para 7');
    expect(plainNote('1d6 [4] → 4 de dano', attributes)).toBe('1d6: 4 para 4 de dano');
    expect(plainNote('3d6 [1, 2, 3] → total 6', attributes)).toBe('3d6: 1, 2 e 3, total 6');
  });

  it('texto sem nada técnico fica como está', () => {
    expect(plainNote('Marco ativado: Chegada à vila.', attributes)).toBe(
      'Marco ativado: Chegada à vila.',
    );
  });
});
