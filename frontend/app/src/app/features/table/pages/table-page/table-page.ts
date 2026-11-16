import { ChangeDetectionStrategy, Component, OnInit, effect, inject, input } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { RouterLink } from '@angular/router';
import { DvButton } from '@shared/ui/button/button';
import { DvDisclosure } from '@shared/ui/disclosure/disclosure';
import { DvNotice } from '@shared/ui/notice/notice';
import { DvState } from '@shared/ui/state/state';
import { ActionDock } from '../../components/action-dock/action-dock';
import { ConnectionBadge } from '../../components/connection-badge/connection-badge';
import { FeedList } from '../../components/feed-list/feed-list';
import { PartyStrip } from '../../components/party-strip/party-strip';
import { SceneCard } from '../../components/scene-card/scene-card';
import { TableStore } from '../../table.store';

/** Tela da mesa: cena, grupo, feed ao vivo e as ações. */
@Component({
  selector: 'dv-table-page',
  imports: [
    RouterLink,
    DvButton,
    DvDisclosure,
    DvNotice,
    DvState,
    ActionDock,
    ConnectionBadge,
    FeedList,
    PartyStrip,
    SceneCard,
  ],
  providers: [TableStore],
  templateUrl: './table-page.html',
  styleUrl: './table-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TablePage implements OnInit {
  readonly tableId = input.required<string>();

  protected readonly store = inject(TableStore);

  private readonly documentTitle = inject(Title);

  constructor() {
    effect(() => this.store.tableId.set(this.tableId()));
    effect(() => {
      const campaign = this.store.title();
      if (campaign) {
        this.documentTitle.setTitle(`${campaign} · Devaneio`);
      }
    });
  }

  ngOnInit(): void {
    this.store.tableId.set(this.tableId()); // os inputs já chegaram; o effect só roda depois
    void this.store.load();
  }
}
