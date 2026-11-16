import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvIcon } from './icon';

@Component({ imports: [DvIcon], template: `<dv-icon name="ok" size="sm" />` })
class Host {}

describe('DvIcon', () => {
  it('é decorativo: escondido do leitor de tela e sem foco', async () => {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const el = (fixture.nativeElement as HTMLElement).querySelector('dv-icon') as HTMLElement;
    expect(el.getAttribute('aria-hidden')).toBe('true');
    expect(el.querySelector('svg')?.getAttribute('focusable')).toBe('false');
    expect(el.querySelector('path')?.getAttribute('d')).toBeTruthy();
    expect(el.classList.contains('icon--sm')).toBe(true);
  });
});
