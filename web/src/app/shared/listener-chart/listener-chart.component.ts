import { Component, Input, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
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

// Listener-count line chart, pure SVG. A min-max band always sits behind, with
// toggleable average / min / max lines on top (average on by default). Drag
// horizontally to zoom into a date window; reset restores the full range.
@Component({
  selector: 'app-listener-chart',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './listener-chart.component.html',
  styleUrls: ['./listener-chart.component.scss'],
})
export class ListenerChartComponent implements OnChanges {
  @Input() points: ListenerPoint[] = [];

  readonly width = 900;
  readonly height = 320;
  readonly padding = { top: 16, right: 20, bottom: 28, left: 36 };

  showAvg = true;
  showMin = false;
  showMax = false;

  // Zoom window as inclusive indices into the full points array.
  viewStart = 0;
  viewEnd = 0;

  plot: PlotPoint[] = [];
  avgPath = '';
  minPath = '';
  maxPath = '';
  bandPath = '';
  monthTicks: MonthTick[] = [];
  yTicks: YTick[] = [];
  peak = 0;

  hover: PlotPoint | null = null;

  // Drag-to-zoom selection (in svg x-coords).
  selecting = false;
  selStartX = 0;
  selCurX = 0;

  private get innerW(): number {
    return this.width - this.padding.left - this.padding.right;
  }
  private get innerH(): number {
    return this.height - this.padding.top - this.padding.bottom;
  }

  get isZoomed(): boolean {
    return this.viewStart > 0 || this.viewEnd < this.points.length - 1;
  }

  ngOnChanges(): void {
    this.viewStart = 0;
    this.viewEnd = Math.max(0, this.points.length - 1);
    this.build();
  }

  private visiblePoints(): ListenerPoint[] {
    return this.points.slice(this.viewStart, this.viewEnd + 1);
  }

  private build(): void {
    const pts = this.visiblePoints();
    if (pts.length === 0) {
      this.plot = [];
      this.avgPath = this.minPath = this.maxPath = this.bandPath = '';
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

    const line = (key: 'yAvg' | 'yMin' | 'yMax') =>
      this.plot.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p[key].toFixed(1)}`).join(' ');
    this.avgPath = line('yAvg');
    this.minPath = line('yMin');
    this.maxPath = line('yMax');

    const top = this.plot.map(p => `${p.x.toFixed(1)} ${p.yMax.toFixed(1)}`);
    const bottom = [...this.plot].reverse().map(p => `${p.x.toFixed(1)} ${p.yMin.toFixed(1)}`);
    this.bandPath = `M ${top.join(' L ')} L ${bottom.join(' L ')} Z`;

    const step = this.niceStep(this.peak);
    this.yTicks = [];
    for (let v = 0; v <= this.peak + 0.001; v += step) {
      this.yTicks.push({ y: yFor(v), label: `${Math.round(v)}` });
    }

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

  private svgX(event: MouseEvent, svg: Element): number {
    const rect = svg.getBoundingClientRect();
    return ((event.clientX - rect.left) / rect.width) * this.width;
  }

  private nearest(x: number): PlotPoint | null {
    if (this.plot.length === 0) return null;
    let best = this.plot[0];
    let bestD = Infinity;
    for (const p of this.plot) {
      const d = Math.abs(p.x - x);
      if (d < bestD) {
        bestD = d;
        best = p;
      }
    }
    return best;
  }

  private nearestIndex(x: number): number {
    let bestI = 0;
    let bestD = Infinity;
    this.plot.forEach((p, i) => {
      const d = Math.abs(p.x - x);
      if (d < bestD) {
        bestD = d;
        bestI = i;
      }
    });
    return bestI;
  }

  onDown(event: MouseEvent, svg: Element): void {
    this.selecting = true;
    this.selStartX = this.selCurX = this.svgX(event, svg);
    this.hover = null;
  }

  onMove(event: MouseEvent, svg: Element): void {
    const x = this.svgX(event, svg);
    if (this.selecting) {
      this.selCurX = x;
    } else {
      this.hover = this.nearest(x);
    }
  }

  onUp(): void {
    if (!this.selecting) return;
    this.selecting = false;
    const lo = Math.min(this.selStartX, this.selCurX);
    const hi = Math.max(this.selStartX, this.selCurX);
    // Ignore tiny drags (treated as a click, not a zoom).
    if (hi - lo < 12) return;
    const startRel = this.nearestIndex(lo);
    const endRel = this.nearestIndex(hi);
    if (endRel - startRel < 1) return;
    const base = this.viewStart;
    this.viewStart = base + startRel;
    this.viewEnd = base + endRel;
    this.build();
  }

  onLeave(): void {
    this.hover = null;
    this.selecting = false;
  }

  resetZoom(): void {
    this.viewStart = 0;
    this.viewEnd = Math.max(0, this.points.length - 1);
    this.build();
  }

  tooltipDate(date: string): string {
    const [y, m, d] = date.split('-');
    const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${names[parseInt(m, 10) - 1]} ${parseInt(d, 10)}, ${y}`;
  }

  get tooltipStyle(): { [k: string]: string } {
    if (!this.hover) return {};
    return { left: `${(this.hover.x / this.width) * 100}%` };
  }

  get selRect(): { x: number; w: number } {
    const lo = Math.min(this.selStartX, this.selCurX);
    const hi = Math.max(this.selStartX, this.selCurX);
    return { x: lo, w: hi - lo };
  }
}
