import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvListEditor, type ListMove } from './list-editor';

@Component({
  imports: [DvListEditor],
  template: `
    <dv-list-editor
      noun="local"
      empty="Sem locais."
      [items]="items()"
      [nameOf]="nameOf"
      (add)="adds = adds + 1"
      (remove)="removed.push($event)"
      (move)="moved.push($event)"
    >
      <ng-template let-item let-index="index">
        <span class="item-form" [attr.data-index]="index">{{ item }}</span>
      </ng-template>
    </dv-list-editor>
  `,
})
class Host {
  readonly items = signal<string[]>(['Vila', 'Floresta', 'Ruínas']);
  nameOf = (item: string): string => item;
  adds = 0;
  removed: number[] = [];
  moved: ListMove[] = [];
}

describe('DvListEditor', () => {
  async function render() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    const button = (label: string) =>
      el.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`) as HTMLButtonElement;
    const settle = async () => {
      fixture.detectChanges();
      await fixture.whenStable();
    };
    return { fixture, el, button, settle, host: fixture.componentInstance };
  }

  it('lista os itens recolhidos, com o nome no título e o formulário projetado com o item e a posição', async () => {
    const { el } = await render();
    const titles = Array.from(el.querySelectorAll('summary')).map((s) => s.textContent?.trim());
    expect(titles).toEqual(['Vila', 'Floresta', 'Ruínas']);
    expect(el.querySelectorAll('details[open]').length).toBe(0);
    const second = el.querySelectorAll('.item-form')[1] as HTMLElement;
    expect(second.textContent).toBe('Floresta');
    expect(second.getAttribute('data-index')).toBe('1');
  });

  it('os botões levam o nome do item e só avisam o pai', async () => {
    const { button, host } = await render();
    button('Remover Floresta').click();
    button('Descer Vila').click();
    button('Subir Ruínas').click();
    expect(host.removed).toEqual([1]);
    expect(host.moved).toEqual([
      { index: 0, delta: 1 },
      { index: 2, delta: -1 },
    ]);
    expect(host.items().length).toBe(3); // quem muda a lista é o pai
  });

  it('subir o primeiro e descer o último ficam bloqueados', async () => {
    const { button } = await render();
    expect(button('Subir Vila').getAttribute('aria-disabled')).toBe('true');
    expect(button('Descer Ruínas').getAttribute('aria-disabled')).toBe('true');
    expect(button('Subir Floresta').getAttribute('aria-disabled')).toBeNull();
  });

  it('acrescentar avisa o pai e o item novo abre sozinho', async () => {
    const { el, settle, host } = await render();
    (el.querySelector('.add') as HTMLButtonElement).click();
    expect(host.adds).toBe(1);
    host.items.update((list) => [...list, 'Novo local']);
    await settle();
    const open = Array.from(el.querySelectorAll('details')).map((d) => d.open);
    expect(open).toEqual([false, false, false, true]);
  });

  it('o botão de acrescentar diz o que acrescenta; sem itens mostra o vazio', async () => {
    const { el, settle, host } = await render();
    expect(el.querySelector('.add')?.textContent).toContain('Acrescentar local');
    host.items.set([]);
    await settle();
    expect(el.textContent).toContain('Sem locais.');
    expect(el.querySelector('ul')).toBeNull();
  });

  it('depois de remover, o foco vai ao botão de acrescentar', async () => {
    const { el, settle, host } = await render();
    const add = el.querySelector('.add') as HTMLButtonElement;
    document.body.append(el);
    host.items.update((list) => list.filter((_, i) => i !== 1));
    await settle();
    await new Promise((resolve) => setTimeout(resolve));
    expect(document.activeElement).toBe(add);
    el.remove();
  });
});
