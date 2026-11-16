import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvDisclosure } from './disclosure';

@Component({
  imports: [DvDisclosure],
  template: `<dv-disclosure label="detalhes" [(open)]="open"
    ><p>Como foi resolvido.</p></dv-disclosure
  >`,
})
class Host {
  readonly open = signal(false);
}

describe('DvDisclosure', () => {
  async function render() {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const details = (fixture.nativeElement as HTMLElement).querySelector(
      'details',
    ) as HTMLDetailsElement;
    return { fixture, details, host: fixture.componentInstance };
  }

  it('nasce fechado, com o resumo e o conteúdo projetado', async () => {
    const { details } = await render();
    expect(details.open).toBe(false);
    expect(details.querySelector('summary')?.textContent).toBe('detalhes');
    expect(details.textContent).toContain('Como foi resolvido.');
  });

  it('abre quando o pai manda e avisa o pai quando o usuário abre', async () => {
    const { fixture, details, host } = await render();
    host.open.set(true);
    await fixture.whenStable();
    expect(details.open).toBe(true);
    host.open.set(false);
    await fixture.whenStable();
    details.open = true;
    details.dispatchEvent(new Event('toggle'));
    expect(host.open()).toBe(true);
  });
});
