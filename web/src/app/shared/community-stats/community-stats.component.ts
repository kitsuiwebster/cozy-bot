import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CozybotService, CommunityStats } from '../../services/cozybot.service';
import { formatHoursMinutes } from '../duration';

interface Bar {
  x: number;
  height: number;
  date: string;
  count: number;
}

// Community-wide numbers for the Stats page: headline tiles, new listeners per
// day, achievement rarity, longest streaks, level spread and sound affinities.
// One request (/community-stats, cached server side).
@Component({
  selector: 'app-community-stats',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './community-stats.component.html',
  styleUrls: ['./community-stats.component.scss'],
})
export class CommunityStatsComponent implements OnInit {
  stats: CommunityStats | null = null;
  failed = false;

  maxAchievementPercent = 1;
  maxLevelCount = 1;
  newUserBars: Bar[] = [];
  newUserTotal = 0;
  private daySlots = 1;
  readonly chartHeight = 140;
  readonly Math = Math;

  constructor(private readonly cozybotService: CozybotService) {}

  ngOnInit(): void {
    this.cozybotService.getCommunityStats().subscribe({
      next: (stats) => {
        this.stats = stats;
        this.maxAchievementPercent = Math.max(1, ...stats.achievements.map(a => a.percent));
        this.maxLevelCount = Math.max(1, ...stats.levels.map(l => l.count));
        this.buildNewUserBars(stats);
      },
      error: (err) => {
        console.error('Error loading community stats:', err);
        this.failed = true;
      },
    });
  }

  private buildNewUserBars(stats: CommunityStats): void {
    const days = stats.new_users.days;
    this.newUserTotal = days.reduce((sum, d) => sum + d.count, 0);
    if (!days.length) {
      this.newUserBars = [];
      return;
    }
    // One slot per calendar day, so quiet days show as gaps instead of vanishing.
    const first = new Date(days[0].date + 'T00:00:00Z').getTime();
    const last = new Date(days[days.length - 1].date + 'T00:00:00Z').getTime();
    const slots = Math.round((last - first) / 86400000) + 1;
    this.daySlots = slots;
    const max = Math.max(...days.map(d => d.count));
    this.newUserBars = days.map(d => ({
      x: Math.round((new Date(d.date + 'T00:00:00Z').getTime() - first) / 86400000) / slots,
      height: (d.count / max) * this.chartHeight,
      date: d.date,
      count: d.count,
    }));
  }

  // Bar width as a share of the chart, leaving a gap between calendar days.
  barWidth(): number {
    return (100 / this.daySlots) * 0.7;
  }

  duration(seconds: number): string {
    return formatHoursMinutes(seconds);
  }

  date(iso: string | null | undefined): string {
    if (!iso) return '';
    return new Date(iso + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
  }

  percent(value: number): string {
    return value < 1 ? value.toFixed(2) : value < 10 ? value.toFixed(1) : value.toFixed(0);
  }
}
