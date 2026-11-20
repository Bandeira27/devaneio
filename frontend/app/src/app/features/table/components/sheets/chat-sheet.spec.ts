import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import type { ChatMessageView } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { SheetRef } from '@shared/ui/sheet/sheet';
import { TableChat } from '../../table.chat';
import { TableStore } from '../../table.store';
import { ChatSheet } from './chat-sheet';

const message = (seq: number, over: Partial<ChatMessageView> = {}): ChatMessageView => ({
  seq,
  player_id: 'p2',
  name: 'Bruno',
  role: 'player',
  text: `mensagem ${seq}`,
  at: 1_700_000_000 + seq,
  ...over,
});

function mount(opts: { messages?: ChatMessageView[]; canChat?: boolean } = {}) {
  const messages = signal(opts.messages ?? []);
  const posted: string[] = [];
  const api = {
    postChat: (_id: string, request: { text: string }) => {
      posted.push(request.text);
      return of(message(99, { player_id: 'p1', text: request.text }));
    },
  };
  const chat = new TableChat(
    api as unknown as ApiClient,
    () => 'a'.repeat(16),
    messages,
    signal('p1'),
    (m) => messages.update((all) => [...all, m]),
  );
  const store = { chat, canChat: signal(opts.canChat ?? true), table: signal({ you: 'p1' }) };
  TestBed.configureTestingModule({
    providers: [
      { provide: TableStore, useValue: store },
      { provide: SheetRef, useValue: { close: vi.fn() } },
    ],
  });
  const fixture = TestBed.createComponent(ChatSheet);
  fixture.detectChanges();
  return { el: fixture.nativeElement as HTMLElement, fixture, posted, chat, messages };
}

const input = (el: HTMLElement) => el.querySelector('input') as HTMLInputElement;

describe('ChatSheet', () => {
  it('mostra as mensagens com nome, selo do anfitrião e a minha marcada', () => {
    const { el } = mount({
      messages: [
        message(1, { player_id: 'p1', name: 'Ana', role: 'host', text: 'vamos?' }),
        message(2),
      ],
    });
    const items = Array.from(el.querySelectorAll('.chat__message'));
    expect(items).toHaveLength(2);
    expect(items[0]?.textContent).toContain('Ana');
    expect(items[0]?.textContent).toContain('anfitrião');
    expect(items[0]?.classList.contains('chat__message--mine')).toBe(true);
    expect(items[1]?.textContent).toContain('mensagem 2');
    expect(items[1]?.textContent).not.toContain('anfitrião');
    expect(el.querySelector('[role="log"]')).not.toBeNull();
  });

  it('sem mensagens explica que a conversa é só do grupo', () => {
    const { el } = mount();
    expect(el.textContent).toContain('o mestre de IA não a lê');
  });

  it('o texto da mensagem vai como texto, nunca como marcação', () => {
    const { el } = mount({ messages: [message(1, { text: '<img src=x onerror=alert(1)>' })] });
    expect(el.querySelector('.chat__text img')).toBeNull();
    expect(el.querySelector('.chat__text')?.textContent).toBe('<img src=x onerror=alert(1)>');
  });

  it('enviar manda o texto sem os espaços das pontas, limpa o campo e mostra a mensagem', async () => {
    const { el, fixture, posted } = mount();
    input(el).value = '  bora pelas ruínas  ';
    input(el).dispatchEvent(new Event('input'));
    fixture.detectChanges();
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(posted).toEqual(['bora pelas ruínas']);
    expect(input(el).value).toBe('');
    expect(el.textContent).toContain('bora pelas ruínas');
  });

  it('um campo vazio não envia nada', async () => {
    const { el, fixture, posted } = mount();
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    await fixture.whenStable();
    expect(posted).toEqual([]);
  });

  it('abrir marca as mensagens como lidas', () => {
    const { chat } = mount({ messages: [message(1), message(2)] });
    expect(chat.unread()).toBe(0);
  });

  it('com a mesa encerrada fica só para ler: sem campo de texto', () => {
    const { el } = mount({ messages: [message(1)], canChat: false });
    expect(el.querySelector('input')).toBeNull();
    expect(el.textContent).toContain('só para ler');
    expect(el.textContent).toContain('mensagem 1');
  });

  it('o limite do campo é o do servidor', () => {
    const { el } = mount();
    expect(input(el).getAttribute('maxlength')).toBe('500');
  });
});
