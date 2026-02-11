import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Title, Meta } from '@angular/platform-browser';
import { CozybotService, CozyUser, LeaderboardResponse, LiveStats } from '../../services/cozybot.service';
import { interval, Subscription } from 'rxjs';
import { LeaderboardHeaderComponent, LeaderboardHeaderStat } from '../../shared/leaderboard-header/leaderboard-header.component';

@Component({
  selector: 'app-cozypoints',
  standalone: true,
  imports: [CommonModule, LeaderboardHeaderComponent],
  templateUrl: './cozypoints.component.html',
  styleUrls: ['./cozypoints.component.scss']
})
export class CozypointsComponent implements OnInit, OnDestroy {
  leaderboard: CozyUser[] = [];
  totalUsersCount = 0;
  headerTotalUsersCount = 0;
  headerTotalTimeSeconds = 0;
  loading = true;
  animatingTitle = false;
  
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

  constructor(
    private readonly cozybotService: CozybotService,
    private readonly titleService: Title,
    private readonly metaService: Meta
  ) {}

  ngOnInit(): void {
    // Set page title and favicon
    this.titleService.setTitle('CozyPoints - CozyBot Discord Bot Points System');
    this.setFavicon('assets/images/cozybot/cozybot-logo3.png');
    this.metaService.updateTag({ name: 'description', content: 'Learn how to earn CozyPoints with CozyBot Discord Bot. Complete guide to the points and achievement system.' });
    
    // Always load users data for header stats
    const cachedUsers = this.cozybotService.getTopUsersCache();
    if (cachedUsers) {
      this.leaderboard = cachedUsers.users;
      this.totalUsersCount = cachedUsers.total_count;
      this.headerTotalUsersCount = cachedUsers.total_count;
      this.headerTotalTimeSeconds = this.getTotalListeningTimeSeconds(cachedUsers.users);
    }
    this.loadUsers();
    this.startLiveStats();
    this.startHeaderStatsRefresh();
  }

  ngOnDestroy(): void {
    if (this.statsSubscription) {
      this.statsSubscription.unsubscribe();
    }
    if (this.headerStatsSubscription) {
      this.headerStatsSubscription.unsubscribe();
    }
  }

  private loadUsers(): void {
    this.loading = true;
    this.cozybotService.getTopUsers().subscribe({
      next: (response: LeaderboardResponse) => {
        this.leaderboard = response.users;
        this.totalUsersCount = response.total_count;
        this.headerTotalUsersCount = response.total_count;
        this.headerTotalTimeSeconds = this.getTotalListeningTimeSeconds(response.users);
        this.loading = false;
        
        // Animer les stats du header au premier chargement
        if (this.leaderboard.length > 0) {
          this.triggerInitialAnimations();
        }
      },
      error: (error) => {
        console.error('Error loading users:', error);
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
    }, 100);
  }

  formatPoints(points: number): string {
    return points.toLocaleString();
  }

  getTotalPoints(): number {
    return this.leaderboard.reduce((total, user) => total + user.total_points, 0);
  }

  getTotalUsers(): number {
    return this.totalUsersCount;
  }

  getHeaderTotalUsers(): number {
    return this.headerTotalUsersCount || this.totalUsersCount;
  }

  getTotalTimeDays(): string {
    const totalSeconds = this.leaderboard.reduce((total, user) => total + user.listening_time_seconds, 0);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    return `${days}d ${hours}h`;
  }

  getHeaderTotalTimeDays(): string {
    const totalSeconds = this.headerTotalTimeSeconds || this.getTotalListeningTimeSeconds(this.leaderboard);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    return `${days}d ${hours}h`;
  }

  private getTotalListeningTimeSeconds(users: CozyUser[]): number {
    return users.reduce((total, user) => total + user.listening_time_seconds, 0);
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

  startLiveStats(): void {
    const cachedStats = this.cozybotService.getLiveStatsCache();
    if (cachedStats) {
      this.liveStats = cachedStats;
      this.previousStats = { ...cachedStats };
      this.statsLoading = false;
    }

    // Charger une première fois immédiatement
    this.loadLiveStats();
    
    // Puis toutes les 5 secondes
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
}
