import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Shell } from './shell';

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
});
