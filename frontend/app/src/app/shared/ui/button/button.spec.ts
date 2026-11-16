import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvButton } from './button';

@Component({
  imports: [DvButton],
  template: `
    <button dvButton type="button">Discreto</button>
    <button dvButton="primary" type="submit">Principal</button>
    <a dvButton="primary" href="#/x">Link</a>
  `,
})
class Host {}

describe('DvButton', () => {
  it('põe a classe base e a variante no botão e no link nativos', async () => {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const [ghost, primary, link] = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('[dvbutton]'),
    );
    expect(ghost?.classList.contains('dv-button')).toBe(true);
    expect(ghost?.classList.contains('dv-button--primary')).toBe(false);
    expect(primary?.classList.contains('dv-button--primary')).toBe(true);
    expect(link?.classList.contains('dv-button--primary')).toBe(true);
    expect(primary?.getAttribute('type')).toBe('submit');
    expect(link?.tagName).toBe('A');
  });
});
