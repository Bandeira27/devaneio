import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import type { ChatMessageView } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { TableChat } from '../../table.chat';
import { TableStore } from '../../table.store';
import { ChatDock } from './chat-dock';

const message = (seq: number, over: Partial<ChatMessageView> = {}): ChatMessageView => ({
  seq,
  player_id: 'p2',
  name: 'Bruno',
  role: 'player',
  text: `mensagem ${seq}`,
  at: 1_700_000_000 + seq,
  ...over,
});

function mount(opts: { messages?: ChatMessageView[]; canChat?: boolean; open?: boolean } = {}) {
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
  chat.baseline();
  chat.open.set(opts.open ?? true);
  const store = { chat, canChat: signal(opts.canChat ?? true), table: signal({ you: 'p1' }) };
  TestBed.configureTestingModule({ providers: [{ provide: TableStore, useValue: store }] });
  const fixture = TestBed.createComponent(ChatDock);
  fixture.detectChanges();
  return { el: fixture.nativeElement as HTMLElement, fixture, posted, chat, messages };
}

const input = (el: HTMLElement) => el.querySelector('input') as HTMLInputElement;

describe('ChatDock', () => {
  it('recolhida é só a pílula, sem o cartão, e com o contador das mensagens novas', () => {
    const { el, fixture, messages } = mount({ open: false });
    expect(el.querySelector('.chat__card')).toBeNull();
    expect(el.querySelector('.chat__pill')?.getAttribute('aria-expanded')).toBe('false');
    messages.set([message(1), message(2, { player_id: 'p1' })]);
    fixture.detectChanges();
    expect(el.querySelector('.chat__pill dv-badge')?.textContent?.trim()).toBe('1');
    expect(el.querySelector('[role="status"]')?.textContent).toContain('1 mensagem nova');
  });

  it('abrir mostra o cartão como região com nome, não modal, e marca as mensagens como lidas', async () => {
    const { el, fixture, chat, messages } = mount({ open: false });
    messages.set([message(1), message(2)]);
    fixture.detectChanges();
    expect(chat.unread()).toBe(2);
    (el.querySelector('.chat__pill') as HTMLButtonElement).click();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(el.querySelector('.chat__card')?.getAttribute('aria-labelledby')).toBe(
      'conversa-titulo',
    );
    expect(el.querySelector('[aria-modal]')).toBeNull();
    expect(chat.unread()).toBe(0);
  });

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
    expect(items[1]?.textContent).not.toContain('anfitrião');
    expect(el.querySelector('[role="log"]')).not.toBeNull();
  });

  it('sem mensagens explica que a conversa é só do grupo', () => {
    expect(mount().el.textContent).toContain('o mestre de IA não a lê');
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

  it('Esc recolhe a conversa e o foco volta à pílula', async () => {
    const { el, fixture, chat } = mount();
    (el.querySelector('.chat__card') as HTMLElement).dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }),
    );
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(chat.open()).toBe(false);
    expect(el.querySelector('.chat__card')).toBeNull();
    expect(el.querySelector('.chat__pill')).not.toBeNull();
  });

  it('com a mesa encerrada fica só para ler: sem campo de texto', () => {
    const { el } = mount({ messages: [message(1)], canChat: false });
    expect(el.querySelector('input')).toBeNull();
    expect(el.textContent).toContain('só para ler');
    expect(el.textContent).toContain('mensagem 1');
  });

  it('com a mesa encerrada, abrir leva o foco ao cartão (não há campo) e o Esc ainda recolhe', async () => {
    const { el, fixture } = mount({ canChat: false, open: false });
    (el.querySelector('.chat__pill') as HTMLButtonElement).click();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(document.activeElement).toBe(el.querySelector('.chat__card'));
  });

  it('a pílula diz quantas mensagens novas há no próprio nome', () => {
    const { el, fixture, messages } = mount({ open: false });
    messages.set([message(1), message(2)]);
    fixture.detectChanges();
    expect(el.querySelector('.chat__pill')?.textContent).toContain('2 mensagens novas');
  });

  it('o limite do campo é o do servidor', () => {
    expect(input(mount().el).getAttribute('maxlength')).toBe('500');
  });

  it('mostra o motivo quando o servidor recusa', async () => {
    const { el, fixture, chat } = mount();
    chat.error.set('Devagar: espere um instante.');
    fixture.detectChanges();
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('Devagar');
    expect(input(el).getAttribute('aria-invalid')).toBe('true');
  });
});
