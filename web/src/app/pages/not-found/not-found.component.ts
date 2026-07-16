import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-not-found',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <main class="not-found">
      <p class="emoji">☔️</p>
      <h1>404</h1>
      <p class="message">Looks like this page drifted off with the rain.</p>
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
      text-align: center;
    }
    .emoji {
      font-size: 2.5rem;
      margin: 0 0 8px;
    }
    h1 {
      font-size: 5rem;
      margin: 0 0 0.5rem;
      font-weight: 700;
      background: var(--gradient-brand);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }
    .message {
      font-size: 1.15rem;
      margin: 0 0 2rem;
      color: var(--color-text-muted);
    }
    a {
      color: var(--color-accent);
      text-decoration: none;
      font-weight: 500;
      padding: 0.75rem 1.5rem;
      background: rgba(var(--color-accent-rgb), 0.1);
      border: 1px solid rgba(var(--color-accent-rgb), 0.2);
      border-radius: var(--radius-sm);
      transition: all 0.2s ease;
      display: inline-block;
    }
    a:hover {
      background: rgba(var(--color-accent-rgb), 0.25);
      border-color: rgba(var(--color-accent-rgb), 0.5);
      color: #ffffff;
      transform: translateY(-2px);
      box-shadow: var(--shadow-glow-strong);
    }
  `]
})
export class NotFoundComponent {}
