import type { TableView } from '@contract/api_responses';

/** O aviso de privacidade do LLM da mesa, ou `''` se o LLM está desligado ou não há aviso. */
export function llmNoticeOf(table: TableView | null): string {
  const llm = table?.llm;
  return llm?.enabled === true && llm.notice ? llm.notice : '';
}
