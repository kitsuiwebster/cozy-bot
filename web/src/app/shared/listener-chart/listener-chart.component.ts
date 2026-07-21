import { Component, Input, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ListenerPoint } from '../../services/cozybot.service';

interface PlotPoint {
  x: number;
  yAvg: number;
  yMin: number;
  yMax: number;
  data: ListenerPoint;
}

interface MonthTick {
  x: number;
  label: string;
}

interface YTick {
  y: number;
  label: string;
}

// Listener-count line chart, pure SVG. One series (daily average) drawn over a
// min-max band, with a crosshair + tooltip on hover. Single series, so the
// title names it and no legend box is needed.
@Component({
  selector: 'app-listener-chart',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './listener-chart.component.html',
  styleUrls: ['./listener-chart.component.scss'],
})
export class ListenerChartComponent implements OnChanges {
  @Input() points: ListenerPoint[] = [];

  readonly width = 900;
  readonly height = 320;
  readonly padding = { top: 16, right: 20, bottom: 28, left: 36 };

  plot: PlotPoint[] = [];
  avgPath = '';
  bandPath = '';
  monthTicks: MonthTick[] = [];
  yTicks: YTick[] = [];
  peak = 0;

  hover: PlotPoint | null = null;

  private get innerW(): number {
    return this.width - this.padding.left - this.padding.right;
  }
  private get innerH(): number {
    return this.height - this.padding.top - this.padding.bottom;
  }

  ngOnChanges(): void {
    this.build();
  }

  private build(): void {
    const pts = this.points || [];
    if (pts.length === 0) {
      this.plot = [];
      this.avgPath = '';
      this.bandPath = '';
      this.monthTicks = [];
      this.yTicks = [];
      return;
    }

    this.peak = Math.max(5, ...pts.map(p => p.max));
    const n = pts.length;

    const xFor = (i: number) => this.padding.left + (n === 1 ? this.innerW / 2 : (i / (n - 1)) * this.innerW);
    const yFor = (v: number) => this.padding.top + this.innerH - (v / this.peak) * this.innerH;

    this.plot = pts.map((p, i) => ({
      x: xFor(i),
      yAvg: yFor(p.avg),
      yMin: yFor(p.min),
      yMax: yFor(p.max),
      data: p,
    }));

    this.avgPath = this.plot.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.yAvg.toFixed(1)}`).join(' ');

    // Band = max line forward, min line back.
    const top = this.plot.map(p => `${p.x.toFixed(1)} ${p.yMax.toFixed(1)}`);
    const bottom = [...this.plot].reverse().map(p => `${p.x.toFixed(1)} ${p.yMin.toFixed(1)}`);
    this.bandPath = `M ${top.join(' L ')} L ${bottom.join(' L ')} Z`;

    // Y axis: a few round gridlines.
    const step = this.niceStep(this.peak);
    this.yTicks = [];
    for (let v = 0; v <= this.peak + 0.001; v += step) {
      this.yTicks.push({ y: yFor(v), label: `${Math.round(v)}` });
    }

    // X axis: one tick per month change.
    this.monthTicks = [];
    let lastMonth = '';
    pts.forEach((p, i) => {
      const month = p.date.slice(0, 7);
      if (month !== lastMonth) {
        lastMonth = month;
        this.monthTicks.push({ x: xFor(i), label: this.monthLabel(p.date) });
      }
    });
  }

  private niceStep(peak: number): number {
    const raw = peak / 4;
    const pow = Math.pow(10, Math.floor(Math.log10(raw)));
    const norm = raw / pow;
    const nice = norm >= 5 ? 5 : norm >= 2 ? 2 : 1;
    return Math.max(1, nice * pow);
  }

  private monthLabel(date: string): string {
    const [y, m] = date.split('-');
    const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const label = names[parseInt(m, 10) - 1];
    return m === '01' ? `${label} ${y}` : label;
  }

  onMove(event: MouseEvent, svg: Element): void {
    if (this.plot.length === 0) return;
    const rect = svg.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * this.width;
    let nearest = this.plot[0];
    let best = Infinity;
    for (const p of this.plot) {
      const d = Math.abs(p.x - x);
      if (d < best) {
        best = d;
        nearest = p;
      }
    }
    this.hover = nearest;
  }

  onLeave(): void {
    this.hover = null;
  }

  tooltipDate(date: string): string {
    const [y, m, d] = date.split('-');
    const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${names[parseInt(m, 10) - 1]} ${parseInt(d, 10)}, ${y}`;
  }

  get tooltipStyle(): { [k: string]: string } {
    if (!this.hover) return {};
    const leftPct = (this.hover.x / this.width) * 100;
    return { left: `${leftPct}%` };
  }
}
