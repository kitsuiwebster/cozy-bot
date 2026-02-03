import { Component, OnInit, OnDestroy, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Title, Meta } from '@angular/platform-browser';
import { CozybotService, CozyUser, LeaderboardResponse, LiveStats, CozyServer, CozySound, ServersResponse, SoundsResponse, UserDetails } from '../../services/cozybot.service';
import { interval, Subscription } from 'rxjs';
import { NgxChartsModule, Color, ScaleType } from '@swimlane/ngx-charts';
import { LeaderboardHeaderComponent, LeaderboardHeaderStat } from '../../shared/leaderboard-header/leaderboard-header.component';

@Component({
  selector: 'app-cozybot',
  standalone: true,
  imports: [CommonModule, FormsModule, NgxChartsModule, LeaderboardHeaderComponent],
  templateUrl: './cozybot.component.html',
  styleUrls: ['./cozybot.component.scss']
})
export class CozybotComponent implements OnInit, OnDestroy {
  leaderboard: CozyUser[] = [];
  servers: CozyServer[] = [];
  sounds: CozySound[] = [];
  
  // Données complètes récupérées de l'API
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
  
  // Pagination
  currentPage = 1;
  pageSize = 30;
  hasNextPage = false;
  hasPreviousPage = false;
  totalPages = 1;
  private readonly pageSizeUsers = 30;
  private readonly pageSizeServers = 50;
  private readonly pageSizeSounds = 30;
  
  // Live stats
  liveStats: LiveStats = { current_listeners: 0, message: '', servers_with_bot: 0, total_servers: 0 };
  previousStats: LiveStats = { current_listeners: 0, message: '', servers_with_bot: 0, total_servers: 0 };
  statsLoading = false;
  animatingListeners = false;
  animatingServers = false;
  
  // Header stats animations
  animatingUsers = false;
  animatingTotalServers = false;
  animatingPoints = false;
  animatingTime = false;
  animatingSessions = false;
  animatingTitle = false;
  
  // Track previous values for animations
  previousTotalServers = 0;
  
  private statsSubscription: Subscription | null = null;
  private headerStatsSubscription: Subscription | null = null;

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

  // Configuration du graphique des sons
  soundsChartData: { name: string; value: number }[] = [];
  soundsByCategoryChartData: { name: string; value: number }[] = [];
  soundsChartTotalTime = 0;
  soundsCategoryTotalTime = 0;
  colorScheme: Color = {
    name: 'soundsColors',
    selectable: true,
    group: ScaleType.Ordinal,
    domain: [
      '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
      '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B195', '#C06C84',
      '#96CEB4', '#FFEAA7', '#DFE6E9', '#74B9FF', '#A29BFE',
      '#FD79A8', '#FDCB6E', '#6C5CE7', '#00B894', '#E17055'
    ]
  };
  chartView: [number, number] = [550, 450];
  showChartLegend = true;

  // Modal pour les détails de l'utilisateur
  showUserModal = false;
  selectedUserDetails: UserDetails | null = null;
  loadingUserDetails = false;

  constructor(
    private cozybotService: CozybotService,
    private titleService: Title,
    private metaService: Meta
  ) {}

  ngOnInit(): void {
    // Set page title and favicon
    this.titleService.setTitle('CozyBot - Discord Bot Leaderboard');
    this.setFavicon('assets/images/cozybot/cozybot-logo3.png');
    this.metaService.updateTag({ name: 'description', content: 'CozyBot Discord Bot leaderboard with real-time stats and CozyPoints system.' });

    // Initialize chart size
    this.updateChartSize();

    // Check URL parameter for view
    const urlParams = new URLSearchParams(window.location.search);
    const viewParam = urlParams.get('view');
    if (viewParam && ['users', 'servers', 'sounds'].includes(viewParam)) {
      this.selectedView = viewParam as 'users' | 'servers' | 'sounds';
    }

    // Always load users data for header stats
    const cachedUsers = this.cozybotService.getTopUsersCache();
    if (cachedUsers) {
      this.leaderboard = cachedUsers.users;
      this.totalUsersCount = cachedUsers.total_count;
      this.headerTotalUsersCount = cachedUsers.total_count;
      this.headerTotalTimeSeconds = this.getTotalListeningTimeSeconds(cachedUsers.users);
    }
    this.loadUsers();
    // Always load sounds data for sessions stats
    this.loadSounds();
    // Then load selected view data
    if (this.selectedView !== 'users' && this.selectedView !== 'sounds') {
      this.loadData();
    }
    this.updatePageSize();
    this.startLiveStats();
    this.startHeaderStatsRefresh();
  }

  onViewChange(): void {
    // Update URL parameter without navigation
    const currentUrl = window.location.pathname;
    const newUrl = `${currentUrl}?view=${this.selectedView}`;
    window.history.replaceState({}, '', newUrl);
    this.currentPage = 1; // Reset to first page when changing view
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

  // Pagination methods
  updatePagination(): void {
    // Calcul simple basé sur les données complètes
    const totalElements = this.selectedView === 'users' ? this.allUsers.length : 
                         this.selectedView === 'servers' ? this.allServers.length : 
                         this.allSounds.length;
    
    this.totalCount = totalElements;
    this.totalPages = Math.ceil(totalElements / this.pageSize);
    this.hasNextPage = this.currentPage < this.totalPages;
    this.hasPreviousPage = this.currentPage > 1;
    
    // Mettre à jour les données affichées pour la page courante
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


  ngOnDestroy(): void {
    if (this.statsSubscription) {
      this.statsSubscription.unsubscribe();
    }
    if (this.headerStatsSubscription) {
      this.headerStatsSubscription.unsubscribe();
    }
  }

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
    this.cozybotService.getTopUsers().subscribe({
      next: (response: LeaderboardResponse) => {
        this.allUsersRaw = response.users;
        this.headerTotalUsersCount = response.total_count;
        this.headerTotalTimeSeconds = this.getTotalListeningTimeSeconds(response.users);
        this.applyUserFilters();

        if (this.selectedView === 'users') {
          this.updatePagination();
        }
        this.loading = false;

        // Animer les stats du header au premier chargement
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
    this.cozybotService.getTopServers().subscribe({
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
    this.cozybotService.getTopSounds().subscribe({
      next: (response: SoundsResponse) => {
        // Filtrer pour ne garder que les sons avec exactement 3 emojis
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

  private triggerInitialAnimations(): void {
    // Délai pour laisser le DOM se mettre à jour
    setTimeout(() => {
      // Animer le titre en premier
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

  // Header stats with animation tracking

  getTotalPoints(): number {
    return this.allUsers.reduce((total, user) => total + user.total_points, 0);
  }

  getTotalUsers(): number {
    return this.totalUsersCount;
  }

  getHeaderTotalUsers(): number {
    return this.headerTotalUsersCount || this.totalUsersCount;
  }

  getTotalTimeDays(): string {
    const totalSeconds = this.allUsers.reduce((total, user) => total + user.listening_time_seconds, 0);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    return `${days}d ${hours}h`;
  }

  getHeaderTotalTimeDays(): string {
    const totalSeconds = this.headerTotalTimeSeconds || this.getTotalListeningTimeSeconds(this.allUsers);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    return `${days}d ${hours}h`;
  }

  private getTotalListeningTimeSeconds(users: CozyUser[]): number {
    return users.reduce((total, user) => total + user.listening_time_seconds, 0);
  }

  getTotalSessions(): number {
    // Calculer le total des sessions à partir des données des sons
    return this.allSounds.reduce((total, sound) => total + sound.total_sessions, 0);
  }

  private startHeaderStatsRefresh(): void {
    // Refresh header totals only every 60 seconds
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
    this.cozybotService.getTopUsers().subscribe({
      next: (response: LeaderboardResponse) => {
        const currentUsers = this.headerTotalUsersCount;
        const newUsers = response.total_count;
        const newTimeSeconds = this.getTotalListeningTimeSeconds(response.users);
        const currentTime = this.getHeaderTotalTimeDays();
        const days = Math.floor(newTimeSeconds / 86400);
        const hours = Math.floor((newTimeSeconds % 86400) / 3600);
        const newTime = `${days}d ${hours}h`;

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
    // Toujours retourner les 3 premiers du classement général (pas de la page courante)
    return this.allUsers.slice(0, 3);
  }

  getRemainingUsers(): CozyUser[] {
    // Toujours afficher tous les utilisateurs en liste (pas de podium)
    return this.leaderboard;
  }

  startLiveStats(): void {
    const cachedStats = this.cozybotService.getLiveStatsCache();
    if (cachedStats) {
      this.liveStats = cachedStats;
      this.previousStats = { ...cachedStats };
      this.statsLoading = false;
    }

    // Charger une première fois immédiatement
    this.loadLiveStats();
    
    // Puis toutes les 5 secondes - uniquement les stats live
    this.statsSubscription = interval(5000).subscribe(() => {
      this.loadLiveStats();
    });
  }

  loadLiveStats(): void {
    this.statsLoading = true;
    this.cozybotService.getLiveStats().subscribe({
      next: (stats: LiveStats) => {
        // Sauvegarder les anciennes stats pour détecter les changements
        this.previousStats = { ...this.liveStats };
        
        // Animer si les valeurs ont changé
        if (this.liveStats.current_listeners !== stats.current_listeners) {
          this.animatingListeners = true;
          setTimeout(() => this.animatingListeners = false, 500);
        }
        if (this.liveStats.servers_with_bot !== stats.servers_with_bot) {
          this.animatingServers = true;
          setTimeout(() => this.animatingServers = false, 500);
        }
        
        this.liveStats = stats;
        this.statsLoading = false;
        
        // Animer Total Servers au premier chargement
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

  getFavoriteSound(user: CozyUser): string {
    return user.favorite_sound || '🌧️🏠🔥';
  }

  getFavoriteSoundEmoji(user: CozyUser | UserDetails): string {
    const favoriteSound = user.favorite_sound || '🌧️🏠🔥';

    // Extraire le premier emoji avec une regex améliorée
    const emojiRegex = /(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}\uFE0F)(?:\u200D(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}\uFE0F))*/u;
    const match = favoriteSound.match(emojiRegex);
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

  /**
   * Compte le nombre d'emojis dans une chaîne de caractères
   */
  private countEmojis(text: string): number {
    // Regex améliorée pour détecter les emojis Unicode, incluant ceux avec ZWJ et modificateurs de peau
    // Cette regex gère les emojis simples, composés (avec ZWJ), et ceux avec modificateurs de peau/variation
    const emojiRegex = /(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}\uFE0F)(?:\u200D(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}\uFE0F))*/gu;
    const matches = text.match(emojiRegex);
    return matches ? matches.length : 0;
  }

  /**
   * Vérifie si un nom de son contient exactement 3 emojis
   */
  private hasThreeEmojis(displayName: string): boolean {
    return this.countEmojis(displayName) === 3;
  }

  /**
   * Prépare les données des sons pour le graphique en camembert
   * Limite aux top 12 sons pour une meilleure visibilité
   */
  private prepareSoundsChartData(): void {
    const topSoundsCount = this.allSounds.length;
    // Trier les sons par temps d'écoute décroissant
    const sortedSounds = [...this.allSounds].sort((a, b) => b.total_time - a.total_time);

    // Prendre les top sons
    const topSounds = sortedSounds.slice(0, topSoundsCount);
    // Créer les données du graphique
    this.soundsChartData = topSounds.map(sound => ({
      name: sound.display_name,
      value: sound.total_time
    }));

    this.soundsChartTotalTime = topSounds.reduce((sum, sound) => sum + sound.total_time, 0);

    // Préparer aussi les données par catégorie
    this.prepareSoundsByCategoryChartData();
  }

  /**
   * Prépare les données des sons regroupés par catégorie (1er emoji)
   */
  private prepareSoundsByCategoryChartData(): void {
    // Regrouper par premier emoji
    const categoriesMap: { [key: string]: number } = {};

    this.allSounds.forEach(sound => {
      // Extraire le premier emoji
      const firstEmoji = this.getFirstEmoji(sound.display_name);
      if (firstEmoji) {
        if (!categoriesMap[firstEmoji]) {
          categoriesMap[firstEmoji] = 0;
        }
        categoriesMap[firstEmoji] += sound.total_time;
      }
    });

    // Convertir en tableau et trier par temps décroissant
    this.soundsByCategoryChartData = Object.entries(categoriesMap)
      .map(([emoji, time]) => ({
        name: `${emoji}\n${this.formatChartValue(time)}`,
        value: time
      }))
      .sort((a, b) => b.value - a.value);

    this.soundsCategoryTotalTime = this.soundsByCategoryChartData.reduce((sum, item) => sum + item.value, 0);
  }

  /**
   * Extrait le premier emoji d'une chaîne de caractères
   */
  private getFirstEmoji(text: string): string {
    const emojiRegex = /(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}\uFE0F)(?:\u200D(?:\p{Emoji_Modifier_Base}\p{Emoji_Modifier}?|\p{Emoji_Presentation}|\p{Emoji}\uFE0F))*/u;
    const match = text.match(emojiRegex);
    return match ? match[0] : '';
  }


  /**
   * Met à jour la taille du graphique en fonction de la taille de l'écran
   */
  @HostListener('window:resize')
  onResize() {
    this.updateChartSize();
  }

  private updateChartSize(): void {
    const width = window.innerWidth;
    if (width <= 768) {
      this.chartView = [350, 320];
      this.showChartLegend = false;
    } else if (width <= 1200) {
      this.chartView = [450, 400];
      this.showChartLegend = true;
    } else {
      this.chartView = [550, 450];
      this.showChartLegend = true;
    }
  }

  /**
   * Formate les labels du graphique pour afficher seulement les emojis (sans le temps)
   */
  formatChartLabel = (label: string): string => {
    // Ne montrer que la première ligne (avant le \n) dans les labels du graphique
    return label.split('\n')[0];
  }

  formatSoundsChartLabel = (label: string): string => label || '';

  formatSoundsTooltipText = (arc: { data?: { name?: string; value?: number } } | null): string => {
    if (!arc || !arc.data) {
      return '';
    }
    const label = arc.data.name || '';
    const value = arc.data.value || 0;
    return `${label} · ${this.formatChartValue(value)} · ${this.formatPercent(value, this.soundsChartTotalTime)}`;
  }

  formatCategoryTooltipText = (arc: { data?: { name?: string; value?: number } } | null): string => {
    if (!arc || !arc.data) {
      return '';
    }
    const rawLabel = arc.data.name || '';
    const label = rawLabel.split('\n')[0];
    const value = arc.data.value || 0;
    return `${label} · ${this.formatChartValue(value)} · ${this.formatPercent(value, this.soundsCategoryTotalTime)}`;
  }

  formatCategoryChartLabel = (label: string): string => {
    return label.split('\n')[0];
  }

  formatPercent = (value: number, total: number): string => {
    if (!total || total <= 0) {
      return '0%';
    }
    const percent = (value / total) * 100;
    return `${percent.toFixed(1)}%`;
  }

  /**
   * Formate la valeur du temps en jours, heures, minutes
   */
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

  /**
   * Ouvre la modal avec les détails de l'utilisateur
   */
  openUserModal(username: string): void {
    this.showUserModal = true;
    this.loadingUserDetails = true;
    this.selectedUserDetails = null;

    this.cozybotService.getUserDetails(username).subscribe({
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

  /**
   * Ferme la modal des détails de l'utilisateur
   */
  closeUserModal(): void {
    this.showUserModal = false;
    this.selectedUserDetails = null;
  }

  /**
   * Formate le temps d'écoute en jours quand plus de 24h
   */
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

  /**
   * Retourne la classe CSS pour le numéro de rang en fonction de l'activité de l'utilisateur
   * Vert: écoute actuellement
   * Jaune: actif récemment (moins d'une semaine)
   * Orange: inactif depuis plus d'une semaine
   * Rouge: inactif depuis plus d'un mois
   */
  getRankColorClass(user: CozyUser): string {
    // Si le user écoute actuellement (current_sound peut être null, undefined, ou une chaîne vide)
    if (user.current_sound !== null && user.current_sound !== undefined && user.current_sound !== '') {
      return 'rank-live';
    }

    const daysSinceActivity = user.days_since_last_activity ?? 0;

    // Plus d'un mois (30 jours)
    if (daysSinceActivity > 30) {
      return 'rank-inactive-month';
    }

    // Plus d'une semaine (7 jours)
    if (daysSinceActivity > 7) {
      return 'rank-inactive-week';
    }

    // Actif récemment
    return 'rank-active';
  }
}
