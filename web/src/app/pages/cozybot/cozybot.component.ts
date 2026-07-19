// =============================================================================
// IMPORTS
// =============================================================================

import { formatDaysHours } from '../../shared/duration';
import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Title, Meta } from '@angular/platform-browser';
import { CozybotService, CozyUser, LeaderboardResponse, LiveStats, CozyServer, CozySound, ServersResponse, SoundsResponse, UserDetails } from '../../services/cozybot.service';
import { interval, Subject, Subscription } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { LeaderboardHeaderComponent, LeaderboardHeaderStat } from '../../shared/leaderboard-header/leaderboard-header.component';

// =============================================================================
// CSS PIE CHARTS
// =============================================================================

interface CssPieSegment {
  name: string;
  color: string;
  valueLabel: string;
  percentLabel: string;
}

interface CssPie {
  gradient: string;
  segments: CssPieSegment[];
  totalLabel: string;
}

// Validated dark-mode categorical palette (fixed slot order, never cycled).
// Gray is reserved for the "Other" fold and deliberately reads as neutral.
const PIE_SERIES_COLORS = ['#3987e5', '#008300', '#d55181', '#c98500', '#199e70', '#d95926', '#9085e9', '#e66767'];
const PIE_OTHER_COLOR = '#8a8a86';
const PIE_TOP_SLICES = 7;

// Color follows the category entity, never its rank.
const PIE_CATEGORIES: { [emoji: string]: { label: string; color: string } } = {
  '🌧️': { label: '🌧️ Rain', color: '#3987e5' },
  '🌊': { label: '🌊 Sea', color: '#199e70' },
  '✨': { label: '✨ Sparkles', color: '#c98500' },
  '🎶': { label: '🎶 Music', color: '#9085e9' },
  '🎵': { label: '🎶 Music', color: '#9085e9' },
  '📡': { label: '📡 Noise', color: '#d55181' },
};

// =============================================================================
// COMPONENT DEFINITION
// =============================================================================

@Component({
  selector: 'app-cozybot',
  standalone: true,
  imports: [CommonModule, FormsModule, LeaderboardHeaderComponent],
  templateUrl: './cozybot.component.html',
  styleUrls: ['./cozybot.component.scss']
})
export class CozybotComponent implements OnInit, OnDestroy {

  // ===========================================================================
  // PROPERTIES - Leaderboard Data
  // ===========================================================================

  leaderboard: CozyUser[] = [];
  servers: CozyServer[] = [];
  sounds: CozySound[] = [];

  allUsers: CozyUser[] = [];
  allUsersRaw: CozyUser[] = [];
  allServers: CozyServer[] = [];
  allSounds: CozySound[] = [];

  totalCount = 0;
  totalUsersCount = 0;
  headerTotalUsersCount = 0;
  headerTotalTimeSeconds = 0;
  loading = true;
  error = '';
  selectedView: 'users' | 'servers' | 'sounds' = 'users';
  showStreakOnly = false;

  // ===========================================================================
  // PROPERTIES - Pagination
  // ===========================================================================

  currentPage = 1;
  pageSize = 30;
  hasNextPage = false;
  hasPreviousPage = false;
  totalPages = 1;
  private readonly pageSizeUsers = 30;
  private readonly pageSizeServers = 50;
  private readonly pageSizeSounds = 30;

  // ===========================================================================
  // PROPERTIES - Live Stats
  // ===========================================================================

  liveStats: LiveStats = { current_listeners: 0, message: '', servers_with_bot: 0, total_servers: 0 };
  previousStats: LiveStats = { current_listeners: 0, message: '', servers_with_bot: 0, total_servers: 0 };
  liveSoundCategories: { emoji: string; count: number }[] = [];
  liveUsernames = new Set<string>();
  statsLoading = false;
  animatingListeners = false;
  animatingServers = false;

  // ===========================================================================
  // PROPERTIES - Header Stats Animations
  // ===========================================================================

  animatingUsers = false;
  animatingTotalServers = false;
  animatingPoints = false;
  animatingTime = false;
  animatingSessions = false;
  animatingTitle = false;

  previousTotalServers = 0;

  private statsSubscription: Subscription | null = null;
  private headerStatsSubscription: Subscription | null = null;
  // Emits on destroy so every inner HTTP subscribe can complete cleanly.
  // Without this, the 5s and 60s polling loops leak in-flight responses that
  // try to update state after the component is gone — visible as CPU drift
  // after the tab stays open for ~30 min.
  private readonly destroy$ = new Subject<void>();

  // ===========================================================================
  // PROPERTIES - Chart Configuration
  // ===========================================================================

  soundsPie: CssPie | null = null;
  categoryPie: CssPie | null = null;

  // ===========================================================================
  // PROPERTIES - User Details Modal
  // ===========================================================================

  showUserModal = false;
  selectedUserDetails: UserDetails | null = null;
  loadingUserDetails = false;

  // ===========================================================================
  // LIFECYCLE METHODS
  // ===========================================================================

  constructor(
    private readonly cozybotService: CozybotService,
    private readonly titleService: Title,
    private readonly metaService: Meta
  ) {}

  ngOnInit(): void {
    this.titleService.setTitle('CozyBot - Discord Bot Leaderboard');
    this.setFavicon('assets/images/cozybot/cozybot-logo3.png');
    this.metaService.updateTag({ name: 'description', content: 'CozyBot Discord Bot leaderboard with real-time stats and CozyPoints system.' });

    const urlParams = new URLSearchParams(globalThis.location.search);
    const viewParam = urlParams.get('view');
    if (viewParam && ['users', 'servers', 'sounds'].includes(viewParam)) {
      this.selectedView = viewParam as 'users' | 'servers' | 'sounds';
    }

    const cachedUsers = this.cozybotService.getTopUsersCache();
    if (cachedUsers) {
      this.leaderboard = cachedUsers.users;
      this.totalUsersCount = cachedUsers.total_count;
      this.headerTotalUsersCount = cachedUsers.total_count;
      this.headerTotalTimeSeconds = this.getTotalListeningTimeSeconds(cachedUsers.users);
    }
    this.loadUsers();
    this.loadSounds();

    if (this.selectedView !== 'users' && this.selectedView !== 'sounds') {
      this.loadData();
    }
    this.updatePageSize();
    this.startLiveStats();
    this.startHeaderStatsRefresh();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    if (this.statsSubscription) {
      this.statsSubscription.unsubscribe();
    }
    if (this.headerStatsSubscription) {
      this.headerStatsSubscription.unsubscribe();
    }
  }

  // ===========================================================================
  // VIEW AND NAVIGATION METHODS
  // ===========================================================================

  onViewChange(): void {
    const currentUrl = globalThis.location.pathname;
    const newUrl = `${currentUrl}?view=${this.selectedView}`;
    globalThis.history.replaceState({}, '', newUrl);
    this.currentPage = 1;
    this.updatePageSize();
    this.loadData();
  }

  onSelectedViewChange(view: string): void {
    if (view === 'users' || view === 'servers' || view === 'sounds') {
      this.selectedView = view;
    }
  }

  manualRefreshCurrentView(): void {
    this.currentPage = 1;
    this.updatePageSize();
    this.loadData();
  }

  getHeaderStats(): LeaderboardHeaderStat[] {
    return [
      {
        value: this.getHeaderTotalUsers(),
        label: 'Total Users',
        animating: this.animatingUsers
      },
      {
        value: this.liveStats.total_servers,
        label: 'Total Servers',
        animating: this.animatingTotalServers
      },
      {
        value: this.getHeaderTotalTimeDays(),
        label: 'Total Time',
        animating: this.animatingTime
      }
    ];
  }

  // ===========================================================================
  // PAGINATION METHODS
  // ===========================================================================

  updatePagination(): void {
    let totalElements: number;
    if (this.selectedView === 'users') {
      totalElements = this.allUsers.length;
    } else if (this.selectedView === 'servers') {
      totalElements = this.allServers.length;
    } else {
      totalElements = this.allSounds.length;
    }

    this.totalCount = totalElements;
    this.totalPages = Math.ceil(totalElements / this.pageSize);
    this.hasNextPage = this.currentPage < this.totalPages;
    this.hasPreviousPage = this.currentPage > 1;

    this.updateDisplayedData();
  }

  updateDisplayedData(): void {
    const startIndex = (this.currentPage - 1) * this.pageSize;
    const endIndex = startIndex + this.pageSize;

    if (this.selectedView === 'users') {
      this.leaderboard = this.allUsers.slice(startIndex, endIndex);
    } else if (this.selectedView === 'servers') {
      this.servers = this.allServers.slice(startIndex, endIndex);
    } else if (this.selectedView === 'sounds') {
      this.sounds = this.allSounds.slice(startIndex, endIndex);
    }
  }

  goToNextPage(): void {
    if (this.hasNextPage) {
      this.currentPage++;
      this.updateDisplayedData();
      this.scrollToTop();
    }
  }

  goToPreviousPage(): void {
    if (this.hasPreviousPage) {
      this.currentPage--;
      this.updateDisplayedData();
      this.scrollToTop();
    }
  }

  goToPage(page: number): void {
    if (page >= 1 && page <= this.totalPages) {
      this.currentPage = page;
      this.updateDisplayedData();
      this.scrollToTop();
    }
  }

  private scrollToTop(): void {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  getPageNumbers(): number[] {
    const pages: number[] = [];
    const maxPages = 5;
    let startPage = Math.max(1, this.currentPage - Math.floor(maxPages / 2));
    let endPage = Math.min(this.totalPages, startPage + maxPages - 1);

    if (endPage - startPage + 1 < maxPages) {
      startPage = Math.max(1, endPage - maxPages + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
      pages.push(i);
    }
    return pages;
  }

  // ===========================================================================
  // DATA LOADING METHODS
  // ===========================================================================

  loadData(): void {
    this.loading = true;
    this.error = '';

    this.updatePageSize();

    if (this.selectedView === 'users') {
      this.loadUsers();
    } else if (this.selectedView === 'servers') {
      this.loadServers();
    } else if (this.selectedView === 'sounds') {
      this.loadSounds();
    }
  }

  private updatePageSize(): void {
    if (this.selectedView === 'users') {
      this.pageSize = this.pageSizeUsers;
    } else if (this.selectedView === 'servers') {
      this.pageSize = this.pageSizeServers;
    } else {
      this.pageSize = this.pageSizeSounds;
    }
  }

  private loadUsers(): void {
    this.loading = this.selectedView === 'users';
    this.cozybotService.getTopUsers().pipe(takeUntil(this.destroy$)).subscribe({
      next: (response: LeaderboardResponse) => {
        this.allUsersRaw = response.users;
        this.headerTotalUsersCount = response.total_count;
        this.headerTotalTimeSeconds = this.getTotalListeningTimeSeconds(response.users);
        this.applyUserFilters();

        if (this.selectedView === 'users') {
          this.updatePagination();
        }
        this.loading = false;

        if (this.allUsers.length > 0) {
          this.triggerInitialAnimations();
        }
      },
      error: (error) => {
        console.error('Error loading users:', error);
        if (this.selectedView === 'users') {
          this.error = 'Failed to load users data';
        }
        this.loading = false;
      }
    });
  }

  setStreakOnly(value: boolean): void {
    this.showStreakOnly = value;
    this.applyUserFilters();
    this.currentPage = 1;
    if (this.selectedView === 'users') {
      this.updatePagination();
    }
  }

  private applyUserFilters(): void {
    const filteredUsers = this.showStreakOnly
      ? this.allUsersRaw.filter(user => (user.daily_streak || 0) > 0)
      : this.allUsersRaw;

    this.allUsers = filteredUsers;
    this.totalUsersCount = filteredUsers.length;
  }

  private loadServers(): void {
    this.cozybotService.getTopServers().pipe(takeUntil(this.destroy$)).subscribe({
      next: (response: ServersResponse) => {
        this.allServers = response.servers;
        this.updatePagination();
        this.loading = false;
      },
      error: (error) => {
        console.error('Error loading servers:', error);
        this.error = 'Failed to load servers data';
        this.loading = false;
      }
    });
  }

  private loadSounds(): void {
    this.cozybotService.getTopSounds().pipe(takeUntil(this.destroy$)).subscribe({
      next: (response: SoundsResponse) => {
        this.allSounds = response.sounds.filter(sound =>
          this.hasThreeEmojis(sound.display_name)
        );

        this.prepareSoundsChartData();
        this.updatePagination();
        this.loading = false;
      },
      error: (error) => {
        console.error('Error loading sounds:', error);
        this.error = 'Failed to load sounds data';
        this.loading = false;
      }
    });
  }

  // ===========================================================================
  // ANIMATION METHODS
  // ===========================================================================

  private triggerInitialAnimations(): void {
    setTimeout(() => {
      this.animatingTitle = true;
      setTimeout(() => this.animatingTitle = false, 800);

      this.animatingUsers = true;
      setTimeout(() => this.animatingUsers = false, 500);

      setTimeout(() => {
        this.animatingPoints = true;
        setTimeout(() => this.animatingPoints = false, 500);
      }, 200);

      setTimeout(() => {
        this.animatingTime = true;
        setTimeout(() => this.animatingTime = false, 500);
      }, 400);

      setTimeout(() => {
        this.animatingSessions = true;
        setTimeout(() => this.animatingSessions = false, 500);
      }, 600);
    }, 100);
  }

  // ===========================================================================
  // STATS CALCULATION METHODS
  // ===========================================================================

  getTotalPoints(): number {
    return this.allUsersRaw.reduce((total, user) => total + user.total_points, 0);
  }

  getTotalUsers(): number {
    return this.totalUsersCount;
  }

  getHeaderTotalUsers(): number {
    return this.headerTotalUsersCount || this.totalUsersCount;
  }

  getTotalTimeDays(): string {
    return formatDaysHours(this.getTotalListeningTimeSeconds(this.allUsersRaw));
  }

  getHeaderTotalTimeDays(): string {
    const totalSeconds = this.headerTotalTimeSeconds || this.getTotalListeningTimeSeconds(this.allUsers);
    return formatDaysHours(totalSeconds);
  }

  private getTotalListeningTimeSeconds(users: CozyUser[]): number {
    return users.reduce((total, user) => total + user.listening_time_seconds, 0);
  }

  getTotalSessions(): number {
    return this.allSounds.reduce((total, sound) => total + sound.total_sessions, 0);
  }

  private startHeaderStatsRefresh(): void {
    this.headerStatsSubscription = interval(60000).subscribe(() => {
      this.refreshTitleAnimation();
      this.refreshHeaderTotals();
    });
  }

  private refreshTitleAnimation(): void {
    this.animatingTitle = true;
    setTimeout(() => this.animatingTitle = false, 800);
  }

  private refreshHeaderTotals(): void {
    this.cozybotService.getTopUsers().pipe(takeUntil(this.destroy$)).subscribe({
      next: (response: LeaderboardResponse) => {
        const currentUsers = this.headerTotalUsersCount;
        const newUsers = response.total_count;
        const newTimeSeconds = this.getTotalListeningTimeSeconds(response.users);
        const currentTime = this.getHeaderTotalTimeDays();
        const newTime = formatDaysHours(newTimeSeconds);

        if (currentUsers !== newUsers) {
          this.animatingUsers = true;
          setTimeout(() => this.animatingUsers = false, 500);
        }

        if (currentTime !== newTime) {
          this.animatingTime = true;
          setTimeout(() => this.animatingTime = false, 500);
        }

        this.headerTotalUsersCount = response.total_count;
        this.headerTotalTimeSeconds = newTimeSeconds;
      },
      error: (error) => {
        console.error('Error refreshing header totals:', error);
      }
    });
  }

  // ===========================================================================
  // LIVE STATS METHODS
  // ===========================================================================

  startLiveStats(): void {
    const cachedStats = this.cozybotService.getLiveStatsCache();
    if (cachedStats) {
      this.liveStats = cachedStats;
      this.previousStats = { ...cachedStats };
      this.liveSoundCategories = this.buildLiveSoundCategories(cachedStats);
      this.liveUsernames = this.buildLiveUsernamesSet(cachedStats);
      this.statsLoading = false;
    }

    this.loadLiveStats();

    this.statsSubscription = interval(5000).subscribe(() => {
      this.loadLiveStats();
    });
  }

  loadLiveStats(): void {
    this.statsLoading = true;
    this.cozybotService.getLiveStats().pipe(takeUntil(this.destroy$)).subscribe({
      next: (stats: LiveStats) => {
        this.previousStats = { ...this.liveStats };

        if (this.liveStats.current_listeners !== stats.current_listeners) {
          this.animatingListeners = true;
          setTimeout(() => this.animatingListeners = false, 500);
        }
        if (this.liveStats.servers_with_bot !== stats.servers_with_bot) {
          this.animatingServers = true;
          setTimeout(() => this.animatingServers = false, 500);
        }

        this.liveStats = stats;
        this.liveSoundCategories = this.buildLiveSoundCategories(stats);
        this.liveUsernames = this.buildLiveUsernamesSet(stats);
        this.statsLoading = false;

        if (this.previousTotalServers === 0) {
          this.previousTotalServers = stats.total_servers;
          setTimeout(() => {
            this.animatingTotalServers = true;
            setTimeout(() => this.animatingTotalServers = false, 500);
          }, 600);
        }
      },
      error: (error) => {
        console.error('Error loading live stats:', error);
        this.statsLoading = false;
      }
    });
  }

  private buildLiveSoundCategories(stats: LiveStats): { emoji: string; count: number }[] {
    const listenersBySound = stats.listeners_by_sound || {};
    const categories: Record<string, number> = {
      '🌧️': 0,
      '🌊': 0,
      '✨': 0,
      '🎶': 0,
      '📡': 0,
      '🎵': 0
    };

    Object.entries(listenersBySound).forEach(([soundName, count]) => {
      let key = '🎵';
      if (soundName.startsWith('rain')) {
        key = '🌧️';
      } else if (soundName.startsWith('sea')) {
        key = '🌊';
      } else if (soundName.startsWith('sparkles')) {
        key = '✨';
      } else if (soundName.startsWith('background-music')) {
        key = '🎶';
      } else if (soundName.startsWith('white-noise') || soundName.startsWith('noise')) {
        key = '📡';
      }
      categories[key] += Number(count) || 0;
    });

    return Object.entries(categories)
      .filter(([, count]) => count > 0)
      .map(([emoji, count]) => ({ emoji, count }));
  }

  private buildLiveUsernamesSet(stats: LiveStats): Set<string> {
    const names = (stats.active_usernames || []).map((name) => name.toLowerCase());
    return new Set(names);
  }

  // ===========================================================================
  // HELPER AND UTILITY METHODS
  // ===========================================================================

  getDisplayName(user: CozyUser): string {
    return user.display_name || user.username;
  }

  trackByUserId(index: number, user: CozyUser): string {
    return user.user_id;
  }

  trackByServerId(index: number, server: CozyServer): string {
    return server.server_id;
  }

  trackBySoundName(index: number, sound: CozySound): string {
    return sound.sound_name;
  }

  formatTime(seconds: number): string {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) {
      return `${days}d ${hours}h`;
    } else if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else {
      return `${minutes}m`;
    }
  }

  formatPoints(points: number): string {
    return points.toLocaleString();
  }

  getRankEmoji(rank: number): string {
    switch (rank) {
      case 1: return '🥇';
      case 2: return '🥈';
      case 3: return '🥉';
      default: return `${rank}.`;
    }
  }

  getListeningTimeDays(seconds: number): string {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    if (days > 0) {
      return `${days}d ${hours}h`;
    }
    if (hours === 0) {
      return '<1h';
    }
    return `${hours}h`;
  }

  getTopThree(): CozyUser[] {
    return this.allUsers.slice(0, 3);
  }

  getRemainingUsers(): CozyUser[] {
    return this.leaderboard;
  }

  getFavoriteSound(user: CozyUser): string {
    return user.favorite_sound || '🌧️🏠🔥';
  }

  getFavoriteSoundEmoji(user: CozyUser | UserDetails): string {
    const favoriteSound = user.favorite_sound || '🌧️🏠🔥';
    const emojiRegex = /(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}\uFE0F)(?:\u200D(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}\uFE0F))*/u;
    const match = emojiRegex.exec(favoriteSound);
    return match ? match[0] : '🌧';
  }

  private setFavicon(iconPath: string): void {
    const link = document.querySelector("link[rel~='icon']") as HTMLLinkElement;
    if (link) {
      link.href = iconPath;
    } else {
      const newLink = document.createElement('link');
      newLink.rel = 'icon';
      newLink.href = iconPath;
      document.getElementsByTagName('head')[0].appendChild(newLink);
    }
  }

  // Returns the CSS class for the rank number based on user activity
  // Green: currently listening
  // Yellow: recently active (less than a week)
  // Orange: inactive for more than a week
  // Red: inactive for more than a month
  getRankColorClass(user: CozyUser): string {
    if (this.liveUsernames.has((user.username || '').toLowerCase())) {
      return 'rank-live';
    }

    const daysSinceActivity = user.days_since_last_activity ?? 0;

    if (daysSinceActivity > 30) {
      return 'rank-inactive-month';
    }

    if (daysSinceActivity > 7) {
      return 'rank-inactive-week';
    }

    return 'rank-active';
  }

  // ===========================================================================
  // EMOJI DETECTION METHODS
  // ===========================================================================

  // Counts the number of emojis in a string
  private countEmojis(text: string): number {
    const emojiRegex = /(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}\uFE0F)(?:\u200D(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}\uFE0F))*/gu;
    const matches = text.match(emojiRegex);
    return matches ? matches.length : 0;
  }

  // Checks if a sound name contains exactly 3 emojis
  private hasThreeEmojis(displayName: string): boolean {
    return this.countEmojis(displayName) === 3;
  }

  // Extracts the first emoji from a string
  private getFirstEmoji(text: string): string {
    const emojiRegex = /(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}\uFE0F)(?:\u200D(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}\uFE0F))*/u;
    const match = emojiRegex.exec(text);
    return match ? match[0] : '';
  }

  // ===========================================================================
  // CHART DATA PREPARATION METHODS
  // ===========================================================================

  // Prepares the per-sound donut: top slices in fixed palette order, the
  // rest folded into a neutral "Other" slice.
  private prepareSoundsChartData(): void {
    const sortedSounds = [...this.allSounds]
      .filter(sound => sound.total_time > 0)
      .sort((a, b) => b.total_time - a.total_time);

    const top = sortedSounds.slice(0, PIE_TOP_SLICES);
    const rest = sortedSounds.slice(PIE_TOP_SLICES);

    const items = top.map((sound, index) => ({
      name: sound.display_name,
      value: sound.total_time,
      color: PIE_SERIES_COLORS[index]
    }));

    if (rest.length > 0) {
      items.push({
        name: `Other (${rest.length} sounds)`,
        value: rest.reduce((sum, sound) => sum + sound.total_time, 0),
        color: PIE_OTHER_COLOR
      });
    }

    this.soundsPie = this.buildCssPie(items);

    this.prepareSoundsByCategoryChartData();
  }

  // Prepares sound data grouped by category (first emoji)
  private prepareSoundsByCategoryChartData(): void {
    const categoriesMap: { [key: string]: number } = {};

    this.allSounds.forEach(sound => {
      const firstEmoji = this.getFirstEmoji(sound.display_name);
      if (firstEmoji) {
        if (!categoriesMap[firstEmoji]) {
          categoriesMap[firstEmoji] = 0;
        }
        categoriesMap[firstEmoji] += sound.total_time;
      }
    });

    // Merge emoji buckets that map to the same category (🎶 and 🎵 are both
    // Music) and give each category its fixed entity color.
    const byCategory: { [label: string]: { value: number; color: string } } = {};
    Object.entries(categoriesMap).forEach(([emoji, time]) => {
      const category = PIE_CATEGORIES[emoji] || { label: emoji, color: PIE_OTHER_COLOR };
      if (!byCategory[category.label]) {
        byCategory[category.label] = { value: 0, color: category.color };
      }
      byCategory[category.label].value += time;
    });

    const items = Object.entries(byCategory)
      .map(([label, entry]) => ({ name: label, value: entry.value, color: entry.color }))
      .sort((a, b) => b.value - a.value);

    this.categoryPie = this.buildCssPie(items);
  }

  // Builds a pure-CSS donut: a conic-gradient with a surface gap between
  // slices, plus precomputed legend rows.
  private buildCssPie(items: { name: string; value: number; color: string }[]): CssPie | null {
    const visible = items.filter(item => item.value > 0);
    const total = visible.reduce((sum, item) => sum + item.value, 0);
    if (visible.length === 0 || total <= 0) {
      return null;
    }

    // ~2px gap at this donut radius; a single full slice needs none.
    const gapDeg = visible.length > 1 ? 1.4 : 0;
    const stops: string[] = [];
    let angle = 0;

    visible.forEach(item => {
      const sweep = (item.value / total) * 360;
      const start = Math.min(angle + gapDeg / 2, angle + sweep);
      const end = Math.max(start, angle + sweep - gapDeg / 2);
      stops.push(`transparent ${angle.toFixed(3)}deg ${start.toFixed(3)}deg`);
      stops.push(`${item.color} ${start.toFixed(3)}deg ${end.toFixed(3)}deg`);
      stops.push(`transparent ${end.toFixed(3)}deg ${(angle + sweep).toFixed(3)}deg`);
      angle += sweep;
    });

    return {
      gradient: `conic-gradient(${stops.join(', ')})`,
      segments: visible.map(item => ({
        name: item.name,
        color: item.color,
        valueLabel: this.formatChartValue(item.value),
        percentLabel: this.formatPercent(item.value, total)
      })),
      totalLabel: this.formatChartValue(total)
    };
  }

  // ===========================================================================
  // CHART CONFIGURATION AND FORMATTING METHODS
  // ===========================================================================

  formatPercent = (value: number, total: number): string => {
    if (!total || total <= 0) {
      return '0%';
    }
    const percent = (value / total) * 100;
    return `${percent.toFixed(1)}%`;
  }

  // Formats time value in days, hours, minutes
  formatChartValue = (value: number): string => {
    const seconds = Math.floor(value);
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    const parts: string[] = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);

    return parts.length > 0 ? parts.join(' ') : '0m';
  }

  // ===========================================================================
  // USER DETAILS MODAL METHODS
  // ===========================================================================

  // Opens the modal with user details
  openUserModal(username: string): void {
    this.showUserModal = true;
    this.loadingUserDetails = true;
    this.selectedUserDetails = null;

    this.cozybotService.getUserDetails(username, true).pipe(takeUntil(this.destroy$)).subscribe({
      next: (details) => {
        this.selectedUserDetails = details;
        this.loadingUserDetails = false;
      },
      error: (err) => {
        console.error('Error loading user details:', err);
        this.loadingUserDetails = false;
        this.closeUserModal();
      }
    });
  }

  // Closes the user details modal
  closeUserModal(): void {
    this.showUserModal = false;
    this.selectedUserDetails = null;
  }

  // Formats listening time in days when more than 24h
  formatListeningTimeDays(seconds: number): string {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) {
      return `${days} day${days > 1 ? 's' : ''} ${hours}h`;
    } else if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else {
      return `${minutes}m`;
    }
  }
}
