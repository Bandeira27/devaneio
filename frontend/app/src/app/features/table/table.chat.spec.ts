import { signal } from '@angular/core';
import { from, of, throwError } from 'rxjs';
import type { ChatMessageView } from '@contract/api_responses';
import type { ApiClient } from '@core/api/api-client';
import { ApiFailure } from '@core/api/api-failure';
import { TableChat } from './table.chat';

const message = (seq: number, playerId = 'p2', text = `m${seq}`): ChatMessageView => ({
  seq,
  player_id: playerId,
  name: 'Bia',
  role: 'player',
  text,
  at: seq,
});

function setup(post: (text: string) => unknown) {
  const messages = signal<ChatMessageView[]>([]);
  const delivered: ChatMessageView[] = [];
  const api = { postChat: (_id: string, request: { text: string }) => post(request.text) };
  const chat = new TableChat(
    api as unknown as ApiClient,
    () => 'a'.repeat(16),
    messages,
    signal('p1'),
    (m) => delivered.push(m),
  );
  return { chat, messages, delivered };
}

describe('TableChat', () => {
  it('conta como não lidas só as mensagens dos outros, e abrir a conversa as marca como lidas', () => {
    const { chat, messages } = setup(() => of(message(1)));
    chat.baseline(); // a mesa já abriu, sem histórico
    messages.set([message(1), message(2, 'p1'), message(3)]);
    expect(chat.unread()).toBe(2); // a do p1 (eu) não conta
    chat.markRead();
    expect(chat.unread()).toBe(0);
    messages.update((all) => [...all, message(4)]);
    expect(chat.unread()).toBe(1);
  });

  it('o histórico da abertura não conta como novidade: só o que chega depois do baseline', () => {
    const { chat, messages } = setup(() => of(message(1)));
    messages.set([message(1), message(2)]);
    expect(chat.unread()).toBe(0); // antes da primeira carga ser dada como vista
    chat.baseline();
    messages.update((all) => [...all, message(3)]);
    expect(chat.unread()).toBe(1);
    chat.baseline(); // só vale a primeira vez
    expect(chat.unread()).toBe(1);
  });

  it('envia, entrega a mensagem ao fluxo ao vivo e limpa o erro', async () => {
    const { chat, delivered } = setup((text) => of(message(7, 'p1', text)));
    expect(await chat.send('bora')).toBe(true);
    expect(delivered.map((m) => m.text)).toEqual(['bora']);
    expect(chat.error()).toBe('');
    expect(chat.busy()).toBe(false);
  });

  it('mostra o motivo quando o servidor recusa e não entrega nada', async () => {
    const { chat, delivered } = setup(() =>
      throwError(
        () => new ApiFailure(429, 'chat_rate_limited', 'devagar: uma mensagem por segundo'),
      ),
    );
    expect(await chat.send('oi')).toBe(false);
    expect(chat.error()).toContain('Devagar');
    expect(delivered).toEqual([]);
    expect(chat.busy()).toBe(false);
  });

  it('não manda duas ao mesmo tempo', async () => {
    let resolve: (value: ChatMessageView) => void = () => undefined;
    const { chat } = setup(() => from(new Promise<ChatMessageView>((r) => (resolve = r))));
    const first = chat.send('um');
    expect(await chat.send('dois')).toBe(false);
    resolve(message(1));
    expect(await first).toBe(true);
  });
});
