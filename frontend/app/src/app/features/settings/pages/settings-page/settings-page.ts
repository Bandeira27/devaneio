import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  OnInit,
  afterNextRender,
  inject,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { DvBadge } from '@shared/ui/badge/badge';
import { DvButton } from '@shared/ui/button/button';
import { DvField } from '@shared/ui/field/field';
import { fieldValue } from '@shared/ui/field/field-value';
import { DvInput } from '@shared/ui/field/input';
import { focusElement } from '@shared/ui/focus';
import { DvIcon } from '@shared/ui/icon/icon';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvOrnament } from '@shared/ui/ornament/ornament';
import { DvState } from '@shared/ui/state/state';
import { LlmSettingsStore } from '../../llm-settings.store';

/**
 * Configuração do LLM (o mestre de IA): endereço, modelo, tempo e chave, com "Testar conexão". É da máquina do servidor,
 * como o roteiro: de fora dela a tela diz que só abre neste computador. A chave só entra; a página nunca a mostra de
 * volta, só se há uma guardada. Vale sem reiniciar o servidor.
 *
 * Foco: erro de validação leva o foco ao primeiro campo com erro; depois de remover, o foco vai ao título, porque o
 * botão tocado some junto com o que ele removia.
 */
@Component({
  selector: 'dv-settings-page',
  imports: [RouterLink, DvBadge, DvButton, DvField, DvIcon, DvInput, DvNotice, DvOrnament, DvState],
  providers: [LlmSettingsStore],
  templateUrl: './settings-page.html',
  styleUrl: './settings-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsPage implements OnInit {
  protected readonly store = inject(LlmSettingsStore);
  protected readonly fieldValue = fieldValue;
  private readonly injector = inject(Injector);
  private readonly heading = viewChild<ElementRef<HTMLElement>>('heading');
  private readonly page = viewChild<ElementRef<HTMLElement>>('page');

  ngOnInit(): void {
    void this.store.load();
  }

  protected async save(): Promise<void> {
    if (!(await this.store.save())) {
      this.focusInvalid();
    }
  }

  protected async saveAndTest(): Promise<void> {
    if (!(await this.store.saveAndTest())) {
      this.focusInvalid();
    }
  }

  protected async clearKey(): Promise<void> {
    if (await this.store.clearKey()) {
      this.focusHeading();
    }
  }

  protected async clearAll(): Promise<void> {
    if (await this.store.clearAll()) {
      this.focusHeading();
    }
  }

  /** Espera a tela mostrar os erros e leva o foco ao primeiro campo marcado como inválido. */
  private focusInvalid(): void {
    afterNextRender(
      () => {
        const field =
          this.page()?.nativeElement.querySelector<HTMLElement>('[aria-invalid="true"]');
        field?.focus();
      },
      { injector: this.injector },
    );
  }

  private focusHeading(): void {
    afterNextRender(
      () => {
        const heading = this.heading()?.nativeElement;
        if (heading !== undefined) {
          focusElement(heading);
        }
      },
      { injector: this.injector },
    );
  }
}
