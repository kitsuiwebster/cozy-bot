import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

export interface LeaderboardHeaderStat {
  value: string | number;
  label: string;
  animating?: boolean;
}

export interface LeaderboardHeaderOption {
  value: string;
  label: string;
}

@Component({
  selector: 'app-leaderboard-header',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './leaderboard-header.component.html',
  styleUrls: ['./leaderboard-header.component.scss']
})
export class LeaderboardHeaderComponent {
  @Input() title = 'CozyBot';
  @Input() subtitle = 'Discord Bot';
  @Input() avatarSrc = 'assets/images/cozybot/cozybot-logo3.png';

  @Input() animatingTitle = false;

  @Input() showViewSelector = false;
  @Input() selectedView = 'users';
  @Output() selectedViewChange = new EventEmitter<string>();
  @Output() viewChange = new EventEmitter<string>();
  @Input() showRefreshButton = false;
  @Output() refresh = new EventEmitter<void>();
  @Input() showUserFilters = false;
  @Input() streakOnly = false;
  @Output() streakOnlyChange = new EventEmitter<boolean>();

  @Input() viewOptions: LeaderboardHeaderOption[] = [
    { value: 'users', label: 'Top Users' },
    { value: 'servers', label: 'Top Servers' },
    { value: 'sounds', label: 'Top Sounds' }
  ];

  @Input() showAddToServer = true;
  @Input() addToServerUrl = 'https://discord.com/oauth2/authorize?client_id=1156917047284994178&permissions=8&scope=bot';
  @Input() addToServerLabel = 'Add to your Discord server';

  @Input() stats: LeaderboardHeaderStat[] = [];

  @Input() statsLoading = false;
  @Input() currentListeners = 0;
  @Input() serversWithBot = 0;
  @Input() animatingListeners = false;
  @Input() animatingServers = false;
  @Input() liveSoundCategories: { emoji: string; count: number }[] = [];

  @Input() ctaHref?: string;
  @Input() ctaText?: string;
  @Input() ctaVariant: 'points' | 'back' = 'points';

  onViewChange(): void {
    this.selectedViewChange.emit(this.selectedView);
    this.viewChange.emit(this.selectedView);
  }

  onRefresh(): void {
    this.refresh.emit();
  }

  onStreakOnlyChange(event: Event): void {
    const input = event.target as HTMLInputElement | null;
    this.streakOnlyChange.emit(!!input?.checked);
  }
}
