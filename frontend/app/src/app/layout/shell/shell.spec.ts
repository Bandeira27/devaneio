import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, TitleStrategy, provideRouter } from '@angular/router';
import { Title } from '@angular/platform-browser';
import { PageTitle } from './page-title';
import { Shell } from './shell';

@Component({ template: '<h1>Entrar na mesa</h1><p>texto</p>' })
class Page {}

describe('Shell', () => {
  async function render(): Promise<HTMLElement> {
    await TestBed.configureTestingModule({
      imports: [Shell],
      providers: [provideRouter([])],
    }).compileComponents();
    const fixture = TestBed.createComponent(Shell);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('mostra a marca como link para a página inicial', async () => {
    const root = await render();
    const brand = root.querySelector('a.shell__brand');
    expect(brand?.textContent?.trim()).toBe('Devaneio');
    expect(brand?.getAttribute('href')).toBe('/');
  });

  it('tem um marco de conteúdo principal com o roteador dentro', async () => {
    const root = await render();
    const main = root.querySelector('main#conteudo');
    expect(main).not.toBeNull();
    expect(main?.querySelector('router-outlet')).not.toBeNull();
    expect(root.querySelector('header')).not.toBeNull();
  });

  it('o link de pular leva o foco ao conteúdo sem mexer na rota', async () => {
    const root = await render();
    const skip = root.querySelector('a.dv-skip') as HTMLAnchorElement;
    expect(skip.textContent?.trim()).toBe('Pular para o conteúdo');
    skip.click();
    expect(document.activeElement).toBe(root.querySelector('main#conteudo'));
  });

  it('depois de navegar, o foco vai para o h1 da nova tela', async () => {
    await TestBed.configureTestingModule({
      imports: [Shell],
      providers: [provideRouter([{ path: 'x', component: Page, title: 'Entrar na mesa' }])],
    }).compileComponents();
    const fixture = TestBed.createComponent(Shell);
    await fixture.whenStable();
    await TestBed.inject(Router).navigateByUrl('/x');
    await fixture.whenStable();
    await new Promise((resolve) => setTimeout(resolve, 5));
    const h1 = (fixture.nativeElement as HTMLElement).querySelector('h1');
    expect(h1).not.toBeNull();
    expect(document.activeElement).toBe(h1);
  });

  it('o título do documento é "Tela · Devaneio", ou só "Devaneio" sem título de rota', async () => {
    await TestBed.configureTestingModule({
      providers: [
        provideRouter([
          { path: 'a', component: Page, title: 'Convite' },
          { path: 'b', component: Page },
        ]),
        { provide: TitleStrategy, useExisting: PageTitle },
      ],
    }).compileComponents();
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/a');
    expect(TestBed.inject(Title).getTitle()).toBe('Convite · Devaneio');
    await router.navigateByUrl('/b');
    expect(TestBed.inject(Title).getTitle()).toBe('Devaneio');
  });
});
