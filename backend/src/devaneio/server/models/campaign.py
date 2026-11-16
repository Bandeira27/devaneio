"""A campanha como o jogador a vê: resumo do catálogo e visão da cena, sem notas privadas."""

from __future__ import annotations

from devaneio.engine import npc_ids_at
from devaneio.schema import (
    BeatStatus,
    Campaign,
    GameState,
    Id,
    StrictModel,
)


class CampaignSummary(StrictModel):
    """Uma campanha do catálogo: id, título e premissa."""

    id: Id
    title: str
    premise: str


def summarize(campaign: Campaign) -> CampaignSummary:
    """O resumo de uma campanha para o catálogo."""
    return CampaignSummary(id=campaign.id, title=campaign.title, premise=campaign.premise)


class ExitView(StrictModel):
    """Uma saída do local atual."""

    id: Id
    name: str


class LocationView(StrictModel):
    """O local atual, com a descrição e as saídas."""

    id: Id
    name: str
    description: str
    exits: list[ExitView]


class NpcInfo(StrictModel):
    """Um NPC que o grupo vê no local."""

    id: Id
    name: str


class BeatInfo(StrictModel):
    """Um marco que já começou."""

    id: Id
    title: str


class FactInfo(StrictModel):
    """Um fato já revelado."""

    id: Id
    text: str
    about: Id | None


class CampaignView(StrictModel):
    """A campanha como um jogador comum a vê.

    Só o que o ``olhar`` do CLI mostra (título, premissa, local atual com saídas, NPCs ali,
    marcos que já começaram e fatos já revelados). Fatos ocultos, ``private_notes``, facções,
    condições dos marcos, atributos, disposição, armas e a localização dos outros NPCs ficam com
    o anfitrião, que recebe a ``Campaign`` inteira.
    """

    id: Id
    title: str
    premise: str
    location: LocationView
    npcs: list[NpcInfo]
    beats: list[BeatInfo]
    facts: list[FactInfo]

    @classmethod
    def of(cls, campaign: Campaign, state: GameState) -> CampaignView:
        """A visão do jogador, derivada da campanha e do estado atual."""
        names = {loc.id: loc.name for loc in campaign.locations}
        here = next(loc for loc in campaign.locations if loc.id == state.current_location_id)
        present = npc_ids_at(state, here.id)
        return cls(
            id=campaign.id,
            title=campaign.title,
            premise=campaign.premise,
            location=LocationView(
                id=here.id,
                name=here.name,
                description=here.description,
                exits=[ExitView(id=c, name=names.get(c, c)) for c in here.connections],
            ),
            npcs=[NpcInfo(id=n.id, name=n.name) for n in campaign.npcs if n.id in present],
            beats=[
                BeatInfo(id=b.id, title=b.title)
                for b in campaign.beats
                if state.beats.get(b.id) not in (None, BeatStatus.PENDING)
            ],
            facts=[
                FactInfo(id=f.id, text=f.text, about=f.about)
                for f in campaign.facts
                if f.id in state.revealed_facts
            ],
        )
