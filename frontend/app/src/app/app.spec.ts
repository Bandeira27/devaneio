import { TestBed } from '@angular/core/testing';
import { App } from './app';

describe('App', () => {
  it('sobe com o roteador', async () => {
    await TestBed.configureTestingModule({ imports: [App] }).compileComponents();
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('router-outlet')).not.toBeNull();
  });
});
