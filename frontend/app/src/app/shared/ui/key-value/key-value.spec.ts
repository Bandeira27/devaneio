import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { DvKeyValue } from './key-value';

@Component({
  imports: [DvKeyValue],
  template: `<dv-key-value [items]="items" />`,
})
class Host {
  items = [
    { label: 'Saídas', value: 'Floresta' },
    { label: 'Aqui', value: 'ninguém' },
  ];
}

describe('DvKeyValue', () => {
  it('é uma lista de definição: cada rótulo é um dt e cada valor um dd', async () => {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(Array.from(el.querySelectorAll('dt')).map((e) => e.textContent)).toEqual([
      'Saídas',
      'Aqui',
    ]);
    expect(Array.from(el.querySelectorAll('dd')).map((e) => e.textContent)).toEqual([
      'Floresta',
      'ninguém',
    ]);
  });
});
