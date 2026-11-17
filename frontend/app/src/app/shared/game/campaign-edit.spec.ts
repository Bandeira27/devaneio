import { hostCampaign } from '../../testing/fixtures';
import {
  addFaction,
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
});
