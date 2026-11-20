import { hostCampaign } from '../../testing/fixtures';
import {
  addBeat,
  addFact,
  addFaction,
  conditionTarget,
  defaultCondition,
  withTarget,
  addLocation,
  addNpc,
  emptyCampaign,
  freeId,
  fromLines,
  moveAt,
  removeItem,
  renameId,
  replaceAt,
  toLines,
} from './campaign-edit';

describe('edição da campanha', () => {
  it('uma campanha em branco tem um local de partida que existe', () => {
    const c = emptyCampaign('nova', 'Nova');
    expect(c.locations.map((l) => l.id)).toEqual([c.start_location_id]);
    expect([c.rules_id, c.narration_id]).toEqual(['default', 'pt-br']);
  });

  it('ids livres saem do nome, sem repetir dentro do tipo', () => {
    const c = addLocation(addLocation(emptyCampaign('n', 'N'), 'Vila Velha'), 'Vila Velha');
    expect(c.locations.map((l) => l.id)).toEqual(['inicio', 'vila-velha', 'vila-velha-2']);
    expect(freeId(c, 'npc', '???')).toBe('npc');
    expect(freeId(c, 'location', 'Início', 'inicio')).toBe('inicio'); // ignora o próprio id
  });

  it('acrescentar nunca muda a campanha que recebeu', () => {
    const base = emptyCampaign('n', 'N');
    addNpc(base);
    addFaction(base);
    expect(base.npcs).toEqual([]);
    expect(base.factions).toEqual([]);
  });

  it('substituir e mover itens de uma lista', () => {
    expect(replaceAt([1, 2, 3], 1, 9)).toEqual([1, 9, 3]);
    expect(moveAt([1, 2, 3], 2, -1)).toEqual([1, 3, 2]);
    expect(moveAt([1, 2, 3], 0, -1)).toEqual([1, 2, 3]);
    expect(moveAt([1, 2, 3], 2, 1)).toEqual([1, 2, 3]);
  });

  it('renomear um local atualiza partida, ligações e NPCs', () => {
    const c = renameId(hostCampaign, 'location', 'vila', 'aldeia');
    expect(c.start_location_id).toBe('aldeia');
    expect(c.locations.some((l) => l.id === 'aldeia')).toBe(true);
    expect(c.locations.flatMap((l) => l.connections)).not.toContain('vila');
    expect(c.npcs.find((n) => n.id === 'ferreiro')?.location_id).toBe('aldeia');
    expect(hostCampaign.start_location_id).toBe('vila'); // a original não muda
  });

  it('renomear um NPC, uma facção ou um marco atualiza quem os cita', () => {
    const withRefs = {
      ...hostCampaign,
      factions: [{ id: 'culto', name: 'Culto', description: '', goals: [], private_notes: [] }],
      npcs: hostCampaign.npcs.map((n) => ({ ...n, faction_id: 'culto' })),
      beats: [
        ...hostCampaign.beats,
        {
          ...(hostCampaign.beats[0] as (typeof hostCampaign.beats)[number]),
          id: 'fim',
          title: 'Fim',
          requires: ['chegada'],
          activate_when: [{ kind: 'beat_done' as const, beat_id: 'chegada' }],
          complete_when: [{ kind: 'npc_down' as const, npc_id: 'ferreiro' }],
        },
      ],
      facts: [{ id: 'f', text: 't', about: 'ferreiro', reveal_when: [] }],
    };
    const a = renameId(withRefs, 'faction', 'culto', 'seita');
    expect(a.npcs.every((n) => n.faction_id === 'seita')).toBe(true);
    const b = renameId(withRefs, 'npc', 'ferreiro', 'bram');
    expect(b.facts[0]?.about).toBe('bram');
    expect(b.beats.find((x) => x.id === 'fim')?.complete_when).toEqual([
      { kind: 'npc_down', npc_id: 'bram' },
    ]);
    const c = renameId(withRefs, 'beat', 'chegada', 'chegou');
    expect(c.beats.find((x) => x.id === 'fim')?.requires).toEqual(['chegou']);
    expect(c.beats.find((x) => x.id === 'fim')?.activate_when).toEqual([
      { kind: 'beat_done', beat_id: 'chegou' },
    ]);
    expect(renameId(withRefs, 'beat', 'chegada', 'chegada')).toBe(withRefs);
  });

  it('remover um local tira as ligações e solta os NPCs; a partida vai para o primeiro que sobra', () => {
    const c = removeItem(hostCampaign, 'location', 'vila');
    expect(c.locations.some((l) => l.id === 'vila')).toBe(false);
    expect(c.locations.flatMap((l) => l.connections)).not.toContain('vila');
    expect(c.npcs.find((n) => n.id === 'ferreiro')?.location_id).toBeNull();
    expect(c.start_location_id).toBe(c.locations[0]?.id);
  });

  it('remover um NPC ou facção solta o que apontava e tira o `about` dos fatos', () => {
    const withFact = {
      ...hostCampaign,
      facts: [{ id: 'f', text: 't', about: 'ferreiro', reveal_when: [] }],
    };
    const c = removeItem(withFact, 'npc', 'ferreiro');
    expect(c.npcs.some((n) => n.id === 'ferreiro')).toBe(false);
    expect(c.facts[0]?.about).toBeNull();
  });

  it('as notas e metas se escrevem uma por linha', () => {
    expect(toLines(' a \n\n b\n')).toEqual(['a', 'b']);
    expect(fromLines(['a', 'b'])).toBe('a\nb');
    expect(toLines(fromLines([]))).toEqual([]);
  });

  it('renomear uma facção atualiza o `about` dos fatos que falam dela', () => {
    const base = {
      ...hostCampaign,
      factions: [{ id: 'culto', name: 'Culto', description: '', goals: [], private_notes: [] }],
      facts: [{ id: 'f', text: 't', about: 'culto', reveal_when: [] }],
    };
    expect(renameId(base, 'faction', 'culto', 'seita').facts[0]?.about).toBe('seita');
  });

  it('remover uma facção ou um marco solta quem os citava', () => {
    const base = {
      ...hostCampaign,
      factions: [{ id: 'culto', name: 'Culto', description: '', goals: [], private_notes: [] }],
      npcs: hostCampaign.npcs.map((n) => ({ ...n, faction_id: 'culto' })),
      facts: [{ id: 'f', text: 't', about: 'culto', reveal_when: [] }],
    };
    const noFaction = removeItem(base, 'faction', 'culto');
    expect(noFaction.factions).toEqual([]);
    expect(noFaction.npcs.every((n) => n.faction_id === null)).toBe(true);
    expect(noFaction.facts[0]?.about).toBeNull();
    const noBeat = removeItem(hostCampaign, 'beat', 'chegada');
    expect(noBeat.beats.some((b) => b.id === 'chegada')).toBe(false);
    expect(noBeat.beats.find((b) => b.id === 'altar')?.requires).toEqual([]);
  });

  it('renomear atualiza as condições de revelar dos fatos e as de local dos marcos', () => {
    const base = {
      ...hostCampaign,
      beats: hostCampaign.beats.map((b) => ({
        ...b,
        activate_when: [{ kind: 'at_location' as const, location_id: 'vila' }],
      })),
      facts: [
        {
          id: 'f',
          text: 't',
          about: null,
          reveal_when: [
            { kind: 'at_location' as const, location_id: 'vila' },
            { kind: 'beat_done' as const, beat_id: 'chegada' },
          ],
        },
      ],
    };
    const c = renameId(renameId(base, 'location', 'vila', 'aldeia'), 'beat', 'chegada', 'chegou');
    expect(c.facts[0]?.reveal_when).toEqual([
      { kind: 'at_location', location_id: 'aldeia' },
      { kind: 'beat_done', beat_id: 'chegou' },
    ]);
    expect(c.beats[0]?.activate_when).toEqual([{ kind: 'at_location', location_id: 'aldeia' }]);
  });

  it('marcos e fatos novos nascem vazios, com id do nome', () => {
    const c = addFact(addBeat(emptyCampaign('n', 'N'), 'A chegada'), 'Bram é do culto');
    expect(c.beats[0]).toMatchObject({ id: 'a-chegada', requires: [], activate_when: [] });
    expect(c.facts[0]).toMatchObject({ id: 'bram-e-do-culto', about: null, reveal_when: [] });
  });

  it('renomear ou remover um fato não mexe no `about` de outros fatos', () => {
    const base = {
      ...hostCampaign,
      facts: [
        { id: 'a', text: 'um', about: null, reveal_when: [] },
        { id: 'b', text: 'dois', about: 'ferreiro', reveal_when: [] },
      ],
    };
    const renamed = renameId(base, 'fact', 'a', 'z');
    expect(renamed.facts.map((f) => f.id)).toEqual(['z', 'b']);
    expect(renamed.facts[1]?.about).toBe('ferreiro');
    expect(removeItem(base, 'fact', 'a').facts.map((f) => f.id)).toEqual(['b']);
  });

  it('a condição padrão de cada tipo aponta para o primeiro item que existe', () => {
    expect(defaultCondition('at_location', hostCampaign, [])).toEqual({
      kind: 'at_location',
      location_id: hostCampaign.locations[0]?.id,
    });
    expect(defaultCondition('npc_down', hostCampaign, [])).toMatchObject({ npc_id: 'ferreiro' });
    expect(defaultCondition('turn_at_least', hostCampaign, [])).toEqual({
      kind: 'turn_at_least',
      turn: 1,
    });
    expect(defaultCondition('check_passed', hostCampaign, ['lutar'])).toEqual({
      kind: 'check_passed',
      skill_id: 'lutar',
      location_id: null,
    });
    expect(defaultCondition('check_passed', hostCampaign, [])).toEqual({
      kind: 'check_passed',
      skill_id: '',
      location_id: null,
    });
  });

  it('o alvo de uma condição vai e volta', () => {
    const cond = defaultCondition('beat_done', hostCampaign, []);
    expect(conditionTarget(withTarget(cond, 'altar'))).toBe('altar');
    expect(withTarget({ kind: 'turn_at_least', turn: 1 }, '4')).toEqual({
      kind: 'turn_at_least',
      turn: 4,
    });
    expect(conditionTarget({ kind: 'turn_at_least', turn: 4 })).toBeNull();
  });

  it('a condição "marco concluído" nunca aponta para o próprio marco', () => {
    expect(defaultCondition('beat_done', hostCampaign, [], 'chegada')).toEqual({
      kind: 'beat_done',
      beat_id: 'altar',
    });
    const alone = { ...hostCampaign, beats: hostCampaign.beats.slice(0, 1) };
    expect(defaultCondition('beat_done', alone, [], 'chegada')).toEqual({
      kind: 'beat_done',
      beat_id: '',
    });
  });

  it('o alvo de uma condição troca em todos os tipos', () => {
    expect(withTarget({ kind: 'at_location', location_id: 'a' }, 'b')).toEqual({
      kind: 'at_location',
      location_id: 'b',
    });
    expect(withTarget({ kind: 'npc_down', npc_id: 'a' }, 'b')).toEqual({
      kind: 'npc_down',
      npc_id: 'b',
    });
    // O local do teste, se a condição o tem, sobrevive à troca da habilidade.
    expect(withTarget({ kind: 'check_passed', skill_id: 'a', location_id: 'vila' }, 'b')).toEqual({
      kind: 'check_passed',
      skill_id: 'b',
      location_id: 'vila',
    });
  });

  it('remover um marco limpa os requisitos dos outros', () => {
    const c = removeItem(hostCampaign, 'beat', 'chegada');
    expect(c.beats.find((b) => b.id === 'altar')?.requires).toEqual([]);
  });
});
