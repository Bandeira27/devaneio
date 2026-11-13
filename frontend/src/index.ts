// Cliente fino: mostra o estado e envia ações. Por enquanto só prova que os tipos
// derivados do contrato (contract/*.schema.json) compilam em modo strict.
import type { Campaign } from "./contract/campaign";
import type { GameState } from "./contract/game_state";

export type { Campaign, GameState };

export function describeTurn(state: GameState, campaign: Campaign): string {
  const location = campaign.locations?.find((l) => l.id === state.current_location_id);
  return `Turno ${state.turn} — ${location?.name ?? state.current_location_id}`;
}
