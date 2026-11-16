/**
 * Os tipos do contrato (`contract/*.schema.json`) que o cliente usa, com nomes curtos. Este arquivo também
 * prova que eles compilam em modo strict.
 */
import type { ApiRequests } from "./contract/api_requests";
import type { ApiResponses } from "./contract/api_responses";
import type { Campaign } from "./contract/campaign";
import type { GameState } from "./contract/game_state";
import type { RuleSystem } from "./contract/rules";

export type { ApiRequests, ApiResponses, Campaign, GameState, RuleSystem };

export type CreateTableRequest = ApiRequests["create_table"];
export type TableView = ApiResponses["table"];

export function describeTurn(state: GameState, campaign: Campaign): string {
  const location = campaign.locations?.find((l) => l.id === state.current_location_id);
  return `Turno ${state.turn} — ${location?.name ?? state.current_location_id}`;
}
