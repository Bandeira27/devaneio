import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvOrnament } from './ornament';

@Component({ imports: [DvOrnament], template: `<dv-ornament />` })
class Host {}

describe('DvOrnament', () => {
  it('é decoração: um SVG escondido do leitor de tela, sem foco', async () => {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const svg = (fixture.nativeElement as HTMLElement).querySelector('svg');
    expect(svg?.getAttribute('aria-hidden')).toBe('true');
    expect(svg?.getAttribute('focusable')).toBe('false');
  });
});
