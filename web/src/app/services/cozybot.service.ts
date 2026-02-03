import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, tap } from 'rxjs';
import { environment } from '../../environments/environment';

export interface CozyUser {
  user_id: string;
  username: string;
  display_name: string;
  total_points: number;
  rank: number;
  listening_time_seconds: number;
  listening_time_formatted: string;
  daily_streak: number;
  level: number;
  level_progress: number;
  sessions_joined: number;
  achievements_count: number;
  favorite_sound?: string;
  current_sound?: string | null;
  days_since_last_activity?: number;
}

export interface LeaderboardResponse {
  users: CozyUser[];
  total_count: number;
}

export interface LiveStats {
  current_listeners: number;
  message: string;
  servers_with_bot: number;
  total_servers: number;
  total_sessions?: number;
  listeners_by_sound?: Record<string, number>;
}

export interface CozyServer {
  server_id: string;
  server_name: string;
  total_time_seconds: number;
  formatted_time: string;
  rank: number;
}

export interface CozySound {
  sound_name: string;
  display_name: string;
  total_time: number;
  formatted_time: string;
  total_sessions: number;
  unique_listeners: number;
}

export interface ServersResponse {
  servers: CozyServer[];
  total_count: number;
}

export interface SoundsResponse {
  sounds: CozySound[];
  total_sounds: number;
}

export interface UserListeningBySound {
  sound_name: string;
  display_name: string;
  total_time: number;
  formatted_time: string;
  session_count: number;
}

export interface UserDetails {
  user_id: string;
  username: string;
  display_name: string;
  total_points: number;
  rank: number;
  level: number;
  level_progress: number;
  listening_time_seconds: number;
  listening_time_formatted: string;
  daily_streak: number;
  sessions_joined: number;
  days_since_last_activity: number;
  last_join_time: string;
  last_active_date: string;
  achievements: string[];
  category_completions: string[];
  favorite_sound: string | null;
  listening_by_sound: UserListeningBySound[];
  current_sound: string | null;
}

@Injectable({
  providedIn: 'root'
})
export class CozybotService {
  private apiUrl = environment.apiUrl;
  private liveStatsCache: LiveStats | null = null;
  private topUsersCache: LeaderboardResponse | null = null;
  private userDetailsCache = new Map<string, UserDetails>();

  constructor(private http: HttpClient) {}

  getTopUsers(): Observable<LeaderboardResponse> {
    return this.http.get<LeaderboardResponse>(`${this.apiUrl}/top-users`).pipe(
      tap((response) => {
        this.topUsersCache = response;
      })
    );
  }

  getLiveStats(): Observable<LiveStats> {
    return this.http.get<LiveStats>(`${this.apiUrl}/total`).pipe(
      tap((stats) => {
        this.liveStatsCache = stats;
      })
    );
  }

  getLiveStatsCache(): LiveStats | null {
    return this.liveStatsCache;
  }

  getTopUsersCache(): LeaderboardResponse | null {
    return this.topUsersCache;
  }

  getTopServers(): Observable<ServersResponse> {
    return this.http.get<ServersResponse>(`${this.apiUrl}/top-servers`);
  }

  getTopSounds(): Observable<SoundsResponse> {
    return this.http.get<SoundsResponse>(`${this.apiUrl}/top-sounds`);
  }

  getUserDetails(username: string): Observable<UserDetails> {
    const cached = this.userDetailsCache.get(username);
    if (cached) {
      return of(cached);
    }
    const encodedUsername = encodeURIComponent(username);
    return this.http.get<UserDetails>(`${this.apiUrl}/user/${encodedUsername}`).pipe(
      tap((details) => {
        this.userDetailsCache.set(username, details);
      })
    );
  }
}
