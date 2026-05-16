import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-not-found',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <main class="not-found">
      <h1>404</h1>
      <p>This page doesn't exist.</p>
      <a routerLink="/cozybot">Back to CozyBot</a>
    </main>
  `,
  styles: [`
    .not-found {
      min-height: 60vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 4rem 1rem;
      color: #fff;
      font-family: system-ui, -apple-system, sans-serif;
      text-align: center;
    }
    h1 { font-size: 5rem; margin: 0 0 0.5rem; font-weight: 700; }
    p { font-size: 1.25rem; margin: 0 0 2rem; opacity: 0.8; }
    a {
      color: #7289da;
      text-decoration: none;
      padding: 0.75rem 1.5rem;
      border: 1px solid currentColor;
      border-radius: 6px;
      transition: background 0.2s;
    }
    a:hover { background: rgba(114, 137, 218, 0.1); }
  `]
})
export class NotFoundComponent {}
