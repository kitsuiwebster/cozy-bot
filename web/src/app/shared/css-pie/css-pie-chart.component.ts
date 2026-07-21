import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CssPie } from './css-pie';

// Pure-CSS donut chart: conic-gradient slices with surface gaps, hero total
// in the hole, and a legend that doubles as the value table.
@Component({
  selector: 'app-css-pie-chart',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="css-pie" *ngIf="pie">
      <h4 class="css-pie-title">{{ title }}</h4>
      <div class="css-pie-figure">
        <div class="css-pie-donut" [style.background]="pie.gradient"></div>
        <div class="css-pie-center">
          <span class="css-pie-total">{{ pie.totalLabel }}</span>
          <span class="css-pie-caption">listened</span>
        </div>
      </div>
      <ul class="css-pie-legend">
        <li *ngFor="let seg of pie.segments">
          <span class="css-pie-dot" [style.background]="seg.color"></span>
          <span class="css-pie-label">{{ seg.name }}</span>
          <span class="css-pie-value">{{ seg.valueLabel }} · {{ seg.percentLabel }}</span>
        </li>
      </ul>
    </div>
  `,
  styleUrls: ['./css-pie-chart.component.scss'],
})
export class CssPieChartComponent {
  @Input() pie: CssPie | null = null;
  @Input() title = '';
}
