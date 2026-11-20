import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import type { ChatMessageView } from '@contract/api_responses';
import { ApiClient } from '@core/api/api-client';
import { TableChat } from '../../table.chat';
import { TableStore } from '../../table.store';
import { ChatDock } from './chat-dock';

const PLAYERS = [
  { id: 'p1', name: 'Ana', role: 'host' as const, character_ids: [] },
  { id: 'p2', name: 'Bruno', role: 'player' as const, character_ids: [] },
  { id: 'p3', name: 'Carla', role: 'player' as const, character_ids: [] },
];

const message = (seq: number, over: Partial<ChatMessageView> = {}): ChatMessageView => ({
  seq,
  player_id: 'p2',
  name: 'Bruno',
  role: 'player',
  text: `mensagem ${seq}`,
  to: null,
  to_name: null,
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
    signal(PLAYERS),
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

  describe('sussurro', () => {
    it('o seletor lista a mesa toda e cada outro jogador, e escolher muda o botão para Sussurrar', () => {
      const { el, fixture } = mount();
      const select = el.querySelector('select') as HTMLSelectElement;
      expect(Array.from(select.options).map((o) => o.textContent?.trim())).toEqual([
        'Para a mesa toda',
        'Sussurro para Bruno',
        'Sussurro para Carla',
      ]);
      expect(el.querySelector('button[type="submit"]')?.textContent?.trim()).toBe('Enviar');
      select.value = 'p3';
      select.dispatchEvent(new Event('change'));
      fixture.detectChanges();
      expect(el.querySelector('button[type="submit"]')?.textContent?.trim()).toBe('Sussurrar');
      expect(el.querySelector('.chat__form--whisper')).not.toBeNull();
    });

    it('um sussurro recebido tem selo "para você", forma própria e botão Responder', () => {
      const { el } = mount({
        messages: [message(1, { to: 'p1', to_name: 'Ana', text: 'psiu' })],
      });
      const item = el.querySelector('.chat__message') as HTMLElement;
      expect(item.classList.contains('chat__message--whisper')).toBe(true);
      expect(item.textContent).toContain('sussurro para você');
      expect(item.querySelector('.chat__reply')?.getAttribute('aria-label')).toBe(
        'Responder em sussurro a Bruno',
      );
    });

    it('um sussurro que eu enviei diz para quem foi e não tem Responder', () => {
      const { el } = mount({
        messages: [message(1, { player_id: 'p1', to: 'p3', to_name: 'Carla', text: 'segredo' })],
      });
      const item = el.querySelector('.chat__message') as HTMLElement;
      expect(item.textContent).toContain('sussurro para Carla');
      expect(item.querySelector('.chat__reply')).toBeNull();
    });

    it('Responder escolhe quem sussurrou como destinatário', () => {
      const { el, fixture, chat } = mount({
        messages: [message(1, { to: 'p1', to_name: 'Ana', text: 'psiu' })],
      });
      (el.querySelector('.chat__reply') as HTMLButtonElement).click();
      fixture.detectChanges();
      expect(chat.recipient()).toBe('p2');
      expect((el.querySelector('select') as HTMLSelectElement).value).toBe('p2');
    });

    it('a pílula diz quantos dos não lidos são sussurros', () => {
      const { el, fixture, messages } = mount({ open: false });
      messages.set([message(1), message(2, { to: 'p1', to_name: 'Ana' })]);
      fixture.detectChanges();
      expect(el.querySelector('.chat__pill')?.textContent).toContain(
        '2 mensagens novas, 1 sussurro para você',
      );
    });

    it('em sussurro o campo diz para quem vai, e que só aquela pessoa vê, mas fica guardado', () => {
      const { el, fixture, chat } = mount();
      chat.sendTo('p3');
      fixture.detectChanges();
      expect(input(el).getAttribute('aria-label')).toBe('Sussurro para Carla');
      expect(el.querySelector('.chat__mode')?.textContent).toContain('Só Carla vê esta mensagem');
      expect(el.querySelector('.chat__mode')?.textContent).toContain('guardada no servidor');
    });

    it('não oferece Responder a quem já não está na mesa', () => {
      const { el } = mount({
        messages: [message(1, { player_id: 'p9', name: 'Fantasma', to: 'p1', to_name: 'Ana' })],
      });
      expect(el.querySelector('.chat__message--whisper')).not.toBeNull();
      expect(el.querySelector('.chat__reply')).toBeNull();
    });

    it('mesa encerrada: sem seletor, sem Responder', () => {
      const { el } = mount({
        canChat: false,
        messages: [message(1, { to: 'p1', to_name: 'Ana' })],
      });
      expect(el.querySelector('select')).toBeNull();
      expect(el.querySelector('.chat__reply')).toBeNull();
    });
  });
});
