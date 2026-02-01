import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Title, Meta } from '@angular/platform-browser';
import { CozybotService, CozyUser, LeaderboardResponse, LiveStats } from '../../services/cozybot.service';
import { interval, Subscription } from 'rxjs';

@Component({
  selector: 'app-credits',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './credits.component.html',
  styleUrls: ['./credits.component.scss']
})
export class CreditsComponent implements OnInit, OnDestroy {
  leaderboard: CozyUser[] = [];
  totalUsersCount = 0;
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

  constructor(
    private cozybotService: CozybotService,
    private titleService: Title,
    private metaService: Meta
  ) {}

  ngOnInit(): void {
    // Set page title and favicon
    this.titleService.setTitle('Credits - CozyBot Discord Bot');
    this.setFavicon('assets/images/cozybot/cozybot-logo3.png');
    this.metaService.updateTag({ name: 'description', content: 'CozyBot Discord Bot credits and development team information. Thank you to all developers who contributed to the project.' });
    
    // Always load users data for header stats
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

  getTotalTimeDays(): string {
    const totalSeconds = this.leaderboard.reduce((total, user) => total + user.listening_time_seconds, 0);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    return `${days}d ${hours}h`;
  }

  private startHeaderStatsRefresh(): void {
    // Refresh header stats en quinconce toutes les 15 secondes
    let counter = 0;
    this.headerStatsSubscription = interval(15000).subscribe(() => {
      const refreshType = counter % 5;
      switch (refreshType) {
        case 0:
          this.refreshTitleAnimation();
          break;
        case 1:
          this.refreshUsersStats();
          break;
        case 2:
          this.refreshServersStats();
          break;
        case 3:
          this.refreshPointsStats();
          break;
        case 4:
          this.refreshTimeStats();
          break;
      }
      counter++;
    });
  }

  private refreshTitleAnimation(): void {
    this.animatingTitle = true;
    setTimeout(() => this.animatingTitle = false, 800);
  }

  private refreshUsersStats(): void {
    this.cozybotService.getTopUsers().subscribe({
      next: (response: LeaderboardResponse) => {
        const currentUsers = this.totalUsersCount;
        const newUsers = response.total_count;
        
        if (currentUsers !== newUsers) {
          this.animatingUsers = true;
          setTimeout(() => this.animatingUsers = false, 500);
        }
        
        this.leaderboard = response.users;
        this.totalUsersCount = response.total_count;
      },
      error: (error) => {
        console.error('Error refreshing users stats:', error);
      }
    });
  }

  private refreshServersStats(): void {
    this.cozybotService.getLiveStats().subscribe({
      next: (stats: LiveStats) => {
        const currentServers = stats.total_servers;
        if (this.previousTotalServers !== currentServers) {
          this.animatingTotalServers = true;
          setTimeout(() => this.animatingTotalServers = false, 500);
          this.previousTotalServers = currentServers;
        }
        this.liveStats = stats;
      },
      error: (error) => {
        console.error('Error refreshing servers stats:', error);
      }
    });
  }

  private refreshPointsStats(): void {
    this.cozybotService.getTopUsers().subscribe({
      next: (response: LeaderboardResponse) => {
        const currentPoints = this.getTotalPoints();
        const newPoints = response.users.reduce((total, user) => total + user.total_points, 0);
        
        if (currentPoints !== newPoints) {
          this.animatingPoints = true;
          setTimeout(() => this.animatingPoints = false, 500);
        }
        
        this.leaderboard = response.users;
        this.totalUsersCount = response.total_count;
      },
      error: (error) => {
        console.error('Error refreshing points stats:', error);
      }
    });
  }

  private refreshTimeStats(): void {
    this.cozybotService.getTopUsers().subscribe({
      next: (response: LeaderboardResponse) => {
        const currentTime = this.getTotalTimeDays();
        const totalSeconds = response.users.reduce((total, user) => total + user.listening_time_seconds, 0);
        const days = Math.floor(totalSeconds / 86400);
        const hours = Math.floor((totalSeconds % 86400) / 3600);
        const newTime = `${days}d ${hours}h`;
        
        if (currentTime !== newTime) {
          this.animatingTime = true;
          setTimeout(() => this.animatingTime = false, 500);
        }
        
        this.leaderboard = response.users;
        this.totalUsersCount = response.total_count;
      },
      error: (error) => {
        console.error('Error refreshing time stats:', error);
      }
    });
  }

  startLiveStats(): void {
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