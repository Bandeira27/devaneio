import { signal } from '@angular/core';
import { from, of, throwError } from 'rxjs';
import type { ChatMessageView, PlayerView } from '@contract/api_responses';
import type { ApiClient } from '@core/api/api-client';
import { ApiFailure } from '@core/api/api-failure';
import { TableChat } from './table.chat';

const message = (seq: number, playerId = 'p2', text = `m${seq}`): ChatMessageView => ({
  seq,
  player_id: playerId,
  name: 'Bia',
  role: 'player',
  text,
  to: null,
  to_name: null,
  at: seq,
});

function setup(post: (text: string) => unknown, players = signal<PlayerView[]>([])) {
  const messages = signal<ChatMessageView[]>([]);
  const delivered: ChatMessageView[] = [];
  const bodies: { text: string; to?: string | null }[] = [];
  const api = {
    postChat: (_id: string, request: { text: string; to?: string | null }) => {
      bodies.push(request);
      return post(request.text);
    },
  };
  const chat = new TableChat(
    api as unknown as ApiClient,
    () => 'a'.repeat(16),
    messages,
    signal('p1'),
    (m) => delivered.push(m),
    players,
  );
  return { chat, messages, delivered, bodies };
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

  describe('sussurro', () => {
    const players = signal<PlayerView[]>([
      { id: 'p1', name: 'Ana', role: 'host', character_ids: [] },
      { id: 'p2', name: 'Bruno', role: 'player', character_ids: [] },
      { id: 'p3', name: 'Carla', role: 'player', character_ids: [] },
    ]);
    const whisper = (seq: number, to: string): ChatMessageView => ({
      ...message(seq),
      to,
      to_name: 'Ana',
    });

    it('os destinatários são os outros jogadores, o anfitrião inclusive, nunca eu', () => {
      const { chat } = setup(() => of(message(1)), players);
      expect(chat.recipients().map((p) => p.id)).toEqual(['p2', 'p3']);
    });

    it('sem escolha a mensagem vai para a mesa toda; escolhido, vai só para aquele jogador', async () => {
      const { chat, bodies } = setup((text) => of(message(1, 'p1', text)), players);
      await chat.send('para todos');
      chat.sendTo('p3');
      await chat.send('só para a Carla');
      chat.sendTo('');
      await chat.send('de novo para todos');
      expect(bodies.map((b) => b.to)).toEqual([null, 'p3', null]);
    });

    it('um sussurro cujo destinatário sumiu não sai para a mesa toda: o envio é recusado com o motivo', async () => {
      const mutable = signal(players());
      const { chat, bodies } = setup((text) => of(message(1, 'p1', text)), mutable);
      chat.sendTo('p3');
      mutable.set(players().filter((p) => p.id !== 'p3'));
      expect(chat.recipientGone()).toBe(true);
      expect(await chat.send('oi')).toBe(false);
      expect(chat.error()).toContain('saiu da mesa');
      expect(bodies).toEqual([]);
    });

    it('conta quantos dos não lidos são sussurros para mim', () => {
      const { chat, messages } = setup(() => of(message(1)), players);
      chat.baseline();
      messages.set([message(1), whisper(2, 'p1'), { ...message(3), to: 'p3', to_name: 'Carla' }]);
      expect(chat.unread()).toBe(3);
      expect(chat.unreadWhispers()).toBe(1); // o de p3 era de outra pessoa (nem chegaria aqui, mas não conta)
    });
  });
});
