import { Routes } from '@angular/router';
import { CozybotComponent } from './pages/cozybot/cozybot.component';
import { CozypointsComponent } from './pages/cozypoints/cozypoints.component';
import { CreditsComponent } from './pages/credits/credits.component';

export const routes: Routes = [
  { path: '', redirectTo: '/cozybot', pathMatch: 'full' },
  { path: 'cozybot', component: CozybotComponent },
  { path: 'cozypoints', component: CozypointsComponent },
  { path: 'cozybot/credits', component: CreditsComponent },
  { path: '**', redirectTo: '/cozybot' }
];
