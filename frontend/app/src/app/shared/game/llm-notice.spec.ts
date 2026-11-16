import type { TableView } from '@contract/api_responses';
import { tableView } from '../../testing/fixtures';
import { llmNoticeOf } from './llm-notice';

const withLlm = (llm: TableView['llm']): TableView => tableView({ llm });

describe('llmNoticeOf', () => {
  it('devolve o aviso quando o LLM está ligado', () => {
    const llm = { enabled: true, description: 'm', notice: 'Vai ao servidor.', secrets: false };
    expect(llmNoticeOf(withLlm(llm))).toBe('Vai ao servidor.');
  });
  it('fica vazio com o LLM desligado, sem aviso ou sem mesa', () => {
    const off = { enabled: false, description: null, notice: 'x', secrets: false };
    const none = { enabled: true, description: 'm', notice: null, secrets: false };
    expect(llmNoticeOf(withLlm(off))).toBe('');
    expect(llmNoticeOf(withLlm(none))).toBe('');
    expect(llmNoticeOf(null)).toBe('');
  });
});
