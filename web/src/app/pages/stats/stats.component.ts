import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Title, Meta } from '@angular/platform-browser';
import { interval, Subscription } from 'rxjs';

import { CozybotService, LiveStats, ListenerPoint, SoundsResponse } from '../../services/cozybot.service';
import { LeaderboardHeaderComponent } from '../../shared/leaderboard-header/leaderboard-header.component';
import { ListenerChartComponent } from '../../shared/listener-chart/listener-chart.component';
import { CssPieChartComponent } from '../../shared/css-pie/css-pie-chart.component';
import { CssPie, buildSoundsPie, buildCategoryPie } from '../../shared/css-pie/css-pie';

@Component({
  selector: 'app-stats',
  standalone: true,
  imports: [CommonModule, LeaderboardHeaderComponent, ListenerChartComponent, CssPieChartComponent],
  templateUrl: './stats.component.html',
  styleUrls: ['./stats.component.scss'],
})
export class StatsComponent implements OnInit, OnDestroy {
  animatingTitle = false;

  liveStats: LiveStats = { current_listeners: 0, message: '', servers_with_bot: 0, total_servers: 0 };
  statsLoading = false;

  listenerPoints: ListenerPoint[] = [];
  soundsPie: CssPie | null = null;
  categoryPie: CssPie | null = null;

  private statsSubscription: Subscription | null = null;

  constructor(
    private readonly cozybotService: CozybotService,
    private readonly titleService: Title,
    private readonly metaService: Meta,
  ) {}

  ngOnInit(): void {
    this.titleService.setTitle('Stats - CozyBot Discord Bot');
    this.setFavicon('assets/images/cozybot/cozybot-logo3.png');
    this.metaService.updateTag({ name: 'description', content: 'CozyBot listening activity over time and sound analytics.' });

    this.loadListeners();
    this.loadSounds();
    this.startLiveStats();
  }

  ngOnDestroy(): void {
    this.statsSubscription?.unsubscribe();
  }

  private loadListeners(): void {
    this.cozybotService.getListenersHistory(400).subscribe({
      next: (res) => { this.listenerPoints = res.points || []; },
      error: (err) => console.error('Error loading listener history:', err),
    });
  }

  private loadSounds(): void {
    this.cozybotService.getTopSounds().subscribe({
      next: (res: SoundsResponse) => {
        const sounds = res.sounds.filter(s => this.countEmojis(s.display_name) === 3);
        this.soundsPie = buildSoundsPie(sounds);
        this.categoryPie = buildCategoryPie(sounds);
      },
      error: (err) => console.error('Error loading sounds:', err),
    });
  }

  private startLiveStats(): void {
    this.loadLiveStats();
    this.statsSubscription = interval(5000).subscribe(() => this.loadLiveStats());
  }

  private loadLiveStats(): void {
    this.cozybotService.getLiveStats().subscribe({
      next: (stats) => { this.liveStats = stats; },
      error: () => {},
    });
  }

  private countEmojis(text: string): number {
    const re = /(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}️)(?:‍(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}️))*/gu;
    return (text.match(re) || []).length;
  }

  private setFavicon(href: string): void {
    let link = document.querySelector("link[rel~='icon']") as HTMLLinkElement | null;
    if (!link) {
      link = document.createElement('link');
      link.rel = 'icon';
      document.head.appendChild(link);
    }
    link.href = href;
  }
}
