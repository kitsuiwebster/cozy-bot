import json
import os
from datetime import datetime, timedelta, timezone, date
from typing import Dict, List, Optional
import asyncio
import logging
import traceback
from utils.storage.couchdb_client import get_couchdb_client


# Streak/day-key helpers — always UTC so a bot running in UTC and a user in any
# timezone see the same day boundary. Without this, a user listening at 23:00 UTC
# could roll over (or not) depending on the host's local tz, breaking streaks.
def _today_utc_key() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _parse_aware(iso_str: str) -> Optional[datetime]:
    """Parse an ISO datetime, treating legacy naive timestamps as UTC."""
    try:
        dt = datetime.fromisoformat(iso_str)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

# Terminal color formatting helpers
def colorize_points(text):
    return f'\033[32m{text}\033[0m'

def colorize_duration(text):
    return f'\033[94m{text}\033[0m'

# Main gamification system class
class CozyGamification:
    def __init__(self):
        # Get CouchDB client
        self.db = get_couchdb_client()

        # Load data from CouchDB
        self.user_data = self.load_user_data()
        self.usernames = self.load_usernames()
        self.servernames = self.load_servernames()

        # Track changes since last save for logging
        self.changes_since_save = {
            'user_listening_time': {},
            'user_sound_time': {},
            'user_points': {},
            'user_points_breakdown': {}
        }

        self.clean_corrupted_data()
        
    def load_user_data(self) -> Dict:
        try:
            data = self.db.load_user_data()
            logging.debug(f'📂 Loaded {len(data)} user records from CouchDB')
            return data
        except Exception as e:
            logging.error(f'❌ Error loading gamification data from CouchDB: {e}')
            return {}

    def load_usernames(self) -> Dict:
        try:
            data = self.db.load_usernames()
            logging.debug(f'📂 Loaded {len(data)} username records from CouchDB')
            return data
        except Exception as e:
            logging.error(f'❌ Error loading usernames from CouchDB: {e}')
            return {}

    def save_usernames(self):
        try:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                # Don't block the event loop
                loop.run_in_executor(None, self.db.save_usernames, self.usernames)
            else:
                self.db.save_usernames(self.usernames)
        except Exception as e:
            logging.error(f'❌ Failed to save usernames to CouchDB: {e}')

    def load_servernames(self) -> Dict:
        try:
            data = self.db.load_servernames()
            logging.debug(f'📂 Loaded {len(data)} server name records from CouchDB')
            return data
        except Exception as e:
            logging.error(f'❌ Error loading servernames from CouchDB: {e}')
            return {}
    
    def save_servernames(self):
        try:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                # Don't block the event loop
                loop.run_in_executor(None, self.db.save_servernames, self.servernames)
            else:
                self.db.save_servernames(self.servernames)
        except Exception as e:
            logging.error(f'❌ Failed to save server names to CouchDB: {e}')
    
    def update_servername(self, guild_id: str, guild_name: str):

        self.servernames[str(guild_id)] = {
            'name': guild_name,
            'last_updated': datetime.now().isoformat()
        }
        self.save_servernames()
    
    def update_username(self, user_id: str, username: str, display_name: str = None, save_immediately: bool = True):

        user_id = str(user_id)
        self.usernames[user_id] = {
            'username': username,
            'display_name': display_name or username,
            'last_updated': datetime.now().isoformat()
        }
        if save_immediately:
            self.save_usernames()
    
    def save_user_data(self, force_detailed_log=False):

        try:
            # Save to CouchDB (SYNC operation - runs in executor to avoid blocking)
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                # Don't block the event loop - save in thread pool
                loop.run_in_executor(None, self.db.save_user_data, self.user_data)
            else:
                self.db.save_user_data(self.user_data)

            from main import format_duration

            has_changes = any(self.changes_since_save['user_listening_time']) or any(self.changes_since_save['user_sound_time']) or any(self.changes_since_save['user_points'])

            if has_changes or force_detailed_log:
                save_type = "PERIODIC SAVE" if force_detailed_log else "EVENT SAVE"
                logging.info(f"✅️ {save_type} - Changes since last save:")

                for user_id in (set(self.changes_since_save['user_listening_time'].keys()) |
                                set(self.changes_since_save['user_sound_time'].keys()) |
                                set(self.changes_since_save['user_points'].keys())):

                    username = f'\033[35m{self.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")}\033[0m'

                    if user_id in self.changes_since_save['user_listening_time']:
                        total_time = self.changes_since_save['user_listening_time'][user_id]
                        if total_time > 0:
                            logging.info(f"  👉 {colorize_duration(f'+{format_duration(total_time)}')} for {username}")

                    if user_id in self.changes_since_save['user_points_breakdown']:
                        breakdown = self.changes_since_save['user_points_breakdown'][user_id]
                        if isinstance(breakdown, list):
                            total_points = sum(item['points'] for item in breakdown if isinstance(item, dict))
                            logging.info(f"  👉 {colorize_points(f'+{total_points} points')} for {username} - Details:")
                            for item in breakdown:
                                if isinstance(item, dict):
                                    item_points = item["points"]
                                    logging.info(f"    ├─ {item['reason']}: {colorize_points(f'+{item_points} pts')}")
                    elif user_id in self.changes_since_save['user_points']:
                        points = self.changes_since_save['user_points'][user_id]
                        if points > 0:
                            logging.info(f"  👉 {colorize_points(f'+{points} points')} for {username}")

                    if (isinstance(self.changes_since_save['user_sound_time'], dict) and
                        user_id in self.changes_since_save['user_sound_time']):
                        user_sound_data = self.changes_since_save['user_sound_time'][user_id]
                        if isinstance(user_sound_data, dict):
                            for sound_name, sound_time in user_sound_data.items():
                                if isinstance(sound_time, (int, float)) and sound_time > 0:
                                    logging.info(f"  👉 {colorize_duration(f'+{format_duration(sound_time)}')} of \033[36m{sound_name}\033[0m for {username}")

                self.changes_since_save = {
                    'user_listening_time': {},
                    'user_sound_time': {},
                    'user_points': {},
                    'user_points_breakdown': {}
                }
            else:
                logging.debug("🚫 EVENT SAVE - No changes since last save")

        except Exception as e:
            logging.error(f'❌ Failed to save gamification data to CouchDB: {e}\n{traceback.format_exc()}')
    
    def get_user_stats(self, user_id: str) -> Dict:

        user_id = str(user_id)
        if self.user_data is None:
            self.user_data = {}
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                'total_points': 0,
                'listening_time': 0.0,
                'sessions_joined': 0,
                'favorite_sounds': {},
                'achievements': [],
                'daily_streak': 0,
                'last_active_date': None,
                'level': 1,
                'level_progress': 0,
            }
        return self.user_data[user_id]

    # Add points and handle leveling up
    def add_points(self, user_id: str, points: int, reason: str = "Listening", save_data: bool = True) -> Dict:

        user_id = str(user_id)
        user_stats = self.get_user_stats(user_id)
        user_stats['total_points'] += points

        old_level = user_stats['level']
        new_level, progress = self.calculate_level(user_stats['total_points'])
        user_stats['level'] = new_level
        user_stats['level_progress'] = progress

        level_up = new_level > old_level
        new_achievements = []
        level_bonus_points = 0

        current_level = old_level
        total_level_bonus_points = 0

        while level_up:
            current_level += 1
            single_level_bonus = current_level * 10
            total_level_bonus_points += single_level_bonus
            user_stats['total_points'] += single_level_bonus

            username = f'\033[35m{self.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")}\033[0m'
            logging.info(f"⭐ Level bonus: {username} reached level {current_level} ({colorize_points(f'+{single_level_bonus} points')})")

            level_achievements = self.check_level_achievements(current_level, user_stats)
            if level_achievements:
                logging.info(f"🏆 Level achievement: {username} unlocked {', '.join(level_achievements)}")
            new_achievements.extend(level_achievements)

            new_level, progress = self.calculate_level(user_stats['total_points'])
            user_stats['level'] = new_level
            user_stats['level_progress'] = progress

            level_up = new_level > current_level

        level_bonus_points = total_level_bonus_points
        new_achievements.extend(self.check_general_achievements(user_stats))

        # Award 100 points per achievement
        achievement_bonus = len(new_achievements) * 100
        if achievement_bonus > 0:
            user_stats['total_points'] += achievement_bonus
            # Recalculate level after achievement bonus
            new_level, progress = self.calculate_level(user_stats['total_points'])
            user_stats['level'] = new_level
            user_stats['level_progress'] = progress
            
            username = f'\033[35m{self.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")}\033[0m'
            logging.info(f"🏆 Achievement bonus: {username} {colorize_points(f'+{achievement_bonus} points')} for {len(new_achievements)} new achievement(s)")
            
            # Track achievement bonus in breakdown
            if user_id not in self.changes_since_save['user_points_breakdown']:
                self.changes_since_save['user_points_breakdown'][user_id] = []
            for achievement in new_achievements:
                self.changes_since_save['user_points_breakdown'][user_id].append({
                    'reason': f'Achievement: {achievement}',
                    'points': 100
                })
        
        # Track points breakdown for regular points - SAFE ACCESS  
        try:
            if not isinstance(self.changes_since_save['user_points_breakdown'], dict):
                self.changes_since_save['user_points_breakdown'] = {}
            if user_id not in self.changes_since_save['user_points_breakdown']:
                self.changes_since_save['user_points_breakdown'][user_id] = []
            if not isinstance(self.changes_since_save['user_points_breakdown'][user_id], list):
                self.changes_since_save['user_points_breakdown'][user_id] = []
            self.changes_since_save['user_points_breakdown'][user_id].append({
                'reason': reason,
                'points': points
            })
        except Exception as e:
            logging.warning(f"⚠️ Error tracking points breakdown: {e} - resetting structures")
            self.changes_since_save['user_points_breakdown'] = {}
        
        if save_data:
            self.save_user_data()
        
        return {
            'points_added': points + achievement_bonus + level_bonus_points,
            'total_points': user_stats['total_points'],
            'level_up': level_up,
            'new_level': new_level if level_up else None,
            'new_achievements': new_achievements,
            'reason': reason
        }
    
    def calculate_level(self, total_points: int) -> tuple:

        # Level progression: level * 10 points needed for next level
        # Level 1->2: 10 pts, Level 2->3: 20 pts, Level 3->4: 30 pts, etc.
        level = 1
        accumulated_points = 0
        
        while True:
            points_needed_for_next = level * level * 50  # Progression quadratique plus difficile
            if accumulated_points + points_needed_for_next > total_points:
                break
            accumulated_points += points_needed_for_next
            level += 1
        
        # Calculate progress towards next level
        points_in_current_level = total_points - accumulated_points
        points_needed_for_next = level * level * 50
        progress = (points_in_current_level / points_needed_for_next) * 100
        
        return level, round(progress, 1)
    
    def add_listening_time(self, user_id: str, seconds: float):

        user_id = str(user_id)
        user_stats = self.get_user_stats(user_id)
        user_stats['listening_time'] += seconds
        
        # Award points: 1 point per minute
        points_to_add = int(seconds / 60)
        if points_to_add > 0:
            return self.add_points(user_id, points_to_add, "Listening time")
        else:
            # Return valid dict even with 0 points to maintain consistency
            return {
                'points_added': 0,
                'total_points': user_stats['total_points'],
                'level_up': False,
                'new_level': None,
                'new_achievements': [],
                'reason': "Listening time"
            }
    
    def track_sound_start(self, user_id: str, sound_name: str, save_immediately: bool = True):

        user_id = str(user_id)
        user_stats = self.get_user_stats(user_id)

        # Note: finalize_current_sound is now handled at the calling site to control timing

        from cogs.audio.sound_mappings import normalize_sound_name
        sound_name = normalize_sound_name(sound_name)

        # Start tracking new sound
        start_time = datetime.now().isoformat()
        user_stats['current_sound'] = {
            'name': sound_name,
            'start_time': start_time
        }

        # Initialize sound stats if not exists
        if 'listening_time_by_sound' not in user_stats:
            user_stats['listening_time_by_sound'] = {}
        if sound_name not in user_stats['listening_time_by_sound']:
            user_stats['listening_time_by_sound'][sound_name] = {
                'total_time': 0.0,
                'session_count': 0,
                'consecutive_time': 0.0
            }

        # Note: consecutive time reset is now handled at guild level via reset_consecutive_time_for_guild

        user_stats['listening_time_by_sound'][sound_name]['session_count'] += 1

        if save_immediately:
            self.save_user_data()
    
    def reset_consecutive_time_for_guild(self, guild_id: str, users_in_vocal: List[str]):

        reset_count = 0
        for user_id in users_in_vocal:
            user_id = str(user_id)
            if user_id in self.user_data:
                user_stats = self.user_data[user_id]
                if 'listening_time_by_sound' in user_stats:
                    for sound_name in user_stats['listening_time_by_sound']:
                        if 'consecutive_time' not in user_stats['listening_time_by_sound'][sound_name]:
                            user_stats['listening_time_by_sound'][sound_name]['consecutive_time'] = 0.0
                        user_stats['listening_time_by_sound'][sound_name]['consecutive_time'] = 0.0
                    reset_count += 1
        
        if reset_count > 0:
            server_name = self.servernames.get(str(guild_id), {}).get('name', f'Server {str(guild_id)[:8]}')
            logging.info(f"👉 Sound change: Reset consecutive time for {reset_count} users in {server_name}")
            self.save_user_data()
    
    def finalize_current_sound(self, user_id: str):

        user_id = str(user_id)
        user_stats = self.get_user_stats(user_id)
        current_sound = user_stats.get('current_sound')

        if current_sound and isinstance(current_sound, dict) and 'start_time' in current_sound:
            try:
                # Capture the session window locally, then clear current_sound *before*
                # crediting. If a concurrent finalize or periodic_backup re-enters for
                # the same user, it sees None and skips — eliminating any chance of
                # double-counting the same time slice into points or listening_time.
                start_time = datetime.fromisoformat(current_sound['start_time'])
                from cogs.audio.sound_mappings import normalize_sound_name
                sound_name = normalize_sound_name(current_sound['name'])
                user_stats['current_sound'] = None

                duration = (datetime.now() - start_time).total_seconds()

                # Cap duration to 30 minutes to prevent corrupted data. Warn so
                # long-listener stats that suddenly plateau become explainable.
                max_duration = 30 * 60  # 30 minutes in seconds
                if duration > max_duration:
                    username = self.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")
                    logging.warning(
                        f"⚠️ Capping session duration for {username} on {sound_name}: "
                        f"{duration/60:.1f}min observed, credited as 30min"
                    )
                    duration = max_duration

                if 'listening_time_by_sound' not in user_stats:
                    user_stats['listening_time_by_sound'] = {}
                if sound_name not in user_stats['listening_time_by_sound']:
                    user_stats['listening_time_by_sound'][sound_name] = {
                        'total_time': 0.0,
                        'session_count': 0,
                        'consecutive_time': 0.0  # Track consecutive session time
                    }
                
                user_stats['listening_time_by_sound'][sound_name]['total_time'] += duration
                # Add to consecutive time for this sound session
                if 'consecutive_time' not in user_stats['listening_time_by_sound'][sound_name]:
                    user_stats['listening_time_by_sound'][sound_name]['consecutive_time'] = 0.0
                user_stats['listening_time_by_sound'][sound_name]['consecutive_time'] += duration
                user_stats['listening_time'] += duration  # Update total listening time
                # current_sound was already cleared above (before crediting) — no need to repeat.

                # Track changes for periodic logging - SAFE ACCESS
                try:
                    if not isinstance(self.changes_since_save['user_listening_time'], dict):
                        self.changes_since_save['user_listening_time'] = {}
                    if user_id not in self.changes_since_save['user_listening_time']:
                        self.changes_since_save['user_listening_time'][user_id] = 0
                    self.changes_since_save['user_listening_time'][user_id] += duration
                    
                    if not isinstance(self.changes_since_save['user_sound_time'], dict):
                        self.changes_since_save['user_sound_time'] = {}
                    if user_id not in self.changes_since_save['user_sound_time']:
                        self.changes_since_save['user_sound_time'][user_id] = {}
                    if not isinstance(self.changes_since_save['user_sound_time'][user_id], dict):
                        self.changes_since_save['user_sound_time'][user_id] = {}
                    if sound_name not in self.changes_since_save['user_sound_time'][user_id]:
                        self.changes_since_save['user_sound_time'][user_id][sound_name] = 0
                    self.changes_since_save['user_sound_time'][user_id][sound_name] += duration
                except Exception as e:
                    logging.warning(f"⚠️ Error updating changes tracking: {e} - resetting structures")
                    self.changes_since_save = {
                        'user_listening_time': {},
                        'user_sound_time': {},
                        'user_points': {},
                        'user_points_breakdown': {}
                    }
                
                points_added = int(duration / 60)
                bonus_points = 0

                # Calculate loyalty bonuses: 30min=+50pts, 1h=+100pts, 12h=+500pts
                consecutive_sound_time = user_stats['listening_time_by_sound'][sound_name]['consecutive_time']
                consecutive_minutes = consecutive_sound_time / 60

                loyalty_bonus = 0
                if consecutive_minutes >= 720:
                    loyalty_bonus = 500
                    reason = f"12h loyalty bonus on {sound_name}"
                    self.add_points(user_id, 500, reason, save_data=False)
                elif consecutive_minutes >= 60:
                    loyalty_bonus = 100
                    reason = f"1h loyalty bonus on {sound_name}"
                    self.add_points(user_id, 100, reason, save_data=False)
                elif consecutive_minutes >= 30:
                    loyalty_bonus = 50
                    reason = f"30min loyalty bonus on {sound_name}"
                    self.add_points(user_id, 50, reason, save_data=False)

                if points_added > 0:
                    self.add_points(user_id, points_added, f"Listening to {sound_name}", save_data=False)

                category_bonus = self.check_category_completion_bonus(user_id, sound_name, save_data=False)
                bonus_points = loyalty_bonus + category_bonus

                from main import format_duration
                duration_str = format_duration(duration)
                username = f'\033[35m{self.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")}\033[0m'
                total_points = points_added + bonus_points
                point_word = "points" if total_points != 1 else "point"
                points_str = f" ({colorize_points(f'+{total_points} {point_word}')})" if total_points > 0 else ""
                bonus_str = f" [{colorize_points(f'+{bonus_points} bonus')}]" if bonus_points > 0 else ""
                logging.info(f"👉 {colorize_duration(f'+{duration_str}')} of \033[36m{sound_name}\033[0m for {username}{points_str}{bonus_str}")

                self.save_user_data()
                
            except Exception as e:
                logging.error(f'❌ Error finalizing sound session: {e}\n{traceback.format_exc()}')
                user_stats['current_sound'] = None
    
    def track_sound_preference(self, user_id: str, sound_name: str):

        self.track_sound_start(user_id, sound_name)
    
    def get_sound_display_name(self, sound_filename: str) -> str:
        from cogs.audio.sound_mappings import get_sound_display_name
        return get_sound_display_name(sound_filename)

    def get_user_favorite_sound(self, user_id: str) -> Optional[str]:

        user_stats = self.get_user_stats(user_id)
        listening_times = user_stats.get('listening_time_by_sound', {})
        
        if not listening_times:
            return None
            
        # Find sound with most time
        favorite = max(listening_times.items(), key=lambda x: x[1]['total_time'])
        if favorite[1]['total_time'] > 0:
            return self.get_sound_display_name(favorite[0])
        return None
    
    def join_session(self, user_id: str, username: str = None, force_bonus: bool = False, save_immediately: bool = True):

        user_id = str(user_id)
        user_stats = self.get_user_stats(user_id)

        # Check for recent join to prevent duplicate points from reconnections
        last_join_time = user_stats.get('last_join_time')
        current_time = datetime.now(timezone.utc)

        # Prevent duplicate join points within 2 minutes
        award_join_points = True
        if not force_bonus and last_join_time:
            last_join = _parse_aware(last_join_time)
            if last_join is not None:
                try:
                    time_since_last_join = (current_time - last_join).total_seconds()
                    if time_since_last_join < 120:
                        award_join_points = False
                except Exception:
                    award_join_points = True

        # Reset consecutive listening time only on a real break (>10 min since last
        # join). Quick reconnects/network blips shouldn't wipe loyalty progress —
        # otherwise the 30min/1h/12h loyalty bonuses become unreachable for anyone
        # who ever drops out mid-session.
        should_reset_consecutive = True
        if last_join_time:
            last_join = _parse_aware(last_join_time)
            if last_join is not None:
                try:
                    gap_seconds = (current_time - last_join).total_seconds()
                    if 0 <= gap_seconds < 600:  # less than 10 minutes
                        should_reset_consecutive = False
                except Exception:
                    pass

        if should_reset_consecutive and 'listening_time_by_sound' in user_stats:
            for sound_name in user_stats['listening_time_by_sound']:
                if 'consecutive_time' not in user_stats['listening_time_by_sound'][sound_name]:
                    user_stats['listening_time_by_sound'][sound_name]['consecutive_time'] = 0.0
                user_stats['listening_time_by_sound'][sound_name]['consecutive_time'] = 0.0

        user_stats['sessions_joined'] += 1
        user_stats['last_join_time'] = current_time.isoformat()

        if username:
            self.update_username(user_id, username, username, save_immediately=save_immediately)

        # Update daily streak (UTC day boundary)
        today = _today_utc_key()
        last_active = user_stats.get('last_active_date')

        if last_active != today:
            if last_active and self.is_consecutive_day(last_active, today):
                user_stats['daily_streak'] += 1
            else:
                user_stats['daily_streak'] = 1
            user_stats['last_active_date'] = today

        result = None
        if award_join_points:
            result = self.add_points(user_id, 5, "Joining session", save_data=save_immediately)
        else:
            result = {
                'points_added': 0,
                'total_points': user_stats['total_points'],
                'level_up': False,
                'new_level': None,
                'new_achievements': [],
                'reason': "Joining session (duplicate prevention)"
            }

        if save_immediately:
            self.save_user_data()
        return result
    
    def is_consecutive_day(self, last_date: str, current_date: str) -> bool:

        try:
            last = datetime.strptime(last_date, '%Y-%m-%d')
            current = datetime.strptime(current_date, '%Y-%m-%d')
            return (current - last).days == 1
        except Exception:
            return False
    
    def get_current_streak(self, user_id: str) -> int:

        user_stats = self.get_user_stats(user_id)
        last_active = user_stats.get('last_active_date')

        if last_active:
            try:
                last = date.fromisoformat(last_active)
                current = datetime.now(timezone.utc).date()
                days_diff = (current - last).days

                if days_diff <= 1:
                    streak = user_stats.get('daily_streak', 0)
                    if streak <= 0:
                        return 1
                    return streak
            except Exception:
                pass

        return 0
    
    def calculate_streak_bonus(self, user_id: str, listening_duration_minutes: float) -> int:

        current_streak = self.get_current_streak(user_id)
        if current_streak <= 0:
            return 0

        # Cap streak at 20 for bonus calculation (actual streak in stats can be unlimited)
        bonus_streak = min(current_streak, 20)

        # +[bonus_streak] points every 10 minutes of listening
        ten_minute_periods = int(listening_duration_minutes / 10)
        if ten_minute_periods > 0:
            return bonus_streak * ten_minute_periods

        return 0
    
    def check_level_achievements(self, level: int, user_stats: Dict) -> List[str]:

        achievements = []
        level_achievements = {
            5: "🥉 Bronze",
            10: "🥈 Silver", 
            15: "🥇 Gold",
            25: "💎 Diamond",
            50: "👑 Master"
        }
        
        achievement = level_achievements.get(level)
        if achievement and achievement not in user_stats['achievements']:
            user_stats['achievements'].append(achievement)
            achievements.append(achievement)
        
        return achievements
    
    def clean_corrupted_data(self):

        cleaned_count = 0

        # Clean user_data - collect IDs to delete first
        corrupted_user_ids = [
            user_id for user_id, stats in self.user_data.items()
            if not isinstance(stats, dict)
        ]

        for user_id in corrupted_user_ids:
            stats = self.user_data[user_id]
            logging.warning(f"⚠️ Removing corrupted user data for {user_id} (type: {type(stats)})")
            del self.user_data[user_id]
            cleaned_count += 1

        # Clean existing user data
        for user_id, stats in self.user_data.items():
                
            # Clean current_sound field
            if 'current_sound' in stats and stats['current_sound'] is not None:
                if not isinstance(stats['current_sound'], dict):
                    logging.warning(f"⚠️ Resetting corrupted current_sound for {user_id}")
                    stats['current_sound'] = None
                    cleaned_count += 1
                elif 'start_time' in stats['current_sound']:
                    try:
                        start_time = datetime.fromisoformat(stats['current_sound']['start_time'])
                        session_duration = (datetime.now() - start_time).total_seconds()
                        # If session is older than 12 hours, it's probably corrupted
                        if session_duration > 12 * 3600:
                            username = self.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")
                            logging.warning(f"⚠️ Resetting old current_sound session for {username}: {session_duration/3600:.1f}h old")
                            stats['current_sound'] = None
                            cleaned_count += 1
                    except Exception:
                        logging.warning(f"⚠️ Resetting corrupted current_sound timestamp for {user_id}")
                        stats['current_sound'] = None
                        cleaned_count += 1
        
        # Clean changes_since_save
        for category, data in self.changes_since_save.items():
            if not isinstance(data, dict):
                logging.warning(f"⚠️ Resetting corrupted {category}")
                self.changes_since_save[category] = {}
                cleaned_count += 1
                
        if cleaned_count > 0:
            logging.info(f"🧹 Cleaned {cleaned_count} corrupted data entries")
            self.save_user_data()
    
    def check_general_achievements(self, user_stats: Dict) -> List[str]:

        achievements = []
        current_achievements = user_stats['achievements']
        
        # Time-based achievements
        hours = user_stats['listening_time'] / 3600
        time_achievements = {
            1: "⏰ First Hour",
            10: "🕐 Dedicated Listener", 
            50: "⏰ Time Master",
            100: "🕰️ Eternal Listener",
            1000: "♾️ Time Lord"
        }
        
        for required_hours, achievement in time_achievements.items():
            if hours >= required_hours and achievement not in current_achievements:
                user_stats['achievements'].append(achievement)
                achievements.append(achievement)
        
        # Streak achievements
        streak = user_stats['daily_streak']
        streak_achievements = {
            7: "🔥 Week Warrior",
            30: "📅 Monthly Master",
            100: "💯 Streak Legend",
            365: "🗓️ Year Champion"
        }
        
        for required_streak, achievement in streak_achievements.items():
            if streak >= required_streak and achievement not in current_achievements:
                user_stats['achievements'].append(achievement)
                achievements.append(achievement)
        
        # Sound preference achievements — read from listening_time_by_sound, which
        # IS populated. The legacy `favorite_sounds` field was never written, making
        # these four achievements permanently unreachable.
        listening_by_sound = user_stats.get('listening_time_by_sound', {})
        if listening_by_sound:
            sound_achievements = {
                "🌧️ Rain Master": "rain",
                "🌊 Sea Master": "sea",
                "✨ Sparkles Master": "sparkles",
                "🎵 Music Master": "background-music",
            }

            for achievement, sound_type in sound_achievements.items():
                if achievement not in current_achievements:
                    sound_count = sum(
                        sound_data.get('session_count', 0)
                        for sound_name, sound_data in listening_by_sound.items()
                        if isinstance(sound_data, dict) and sound_type in sound_name.lower()
                    )
                    if sound_count >= 50:
                        user_stats['achievements'].append(achievement)
                        achievements.append(achievement)
        
        return achievements
    
    def check_category_completion_bonus(self, user_id: str, sound_name: str, save_data: bool = True) -> int:

        user_id = str(user_id)
        user_stats = self.get_user_stats(user_id)
        listening_times = user_stats.get('listening_time_by_sound', {})
        
        # Get category from sound name
        category = None
        if 'rain' in sound_name:
            category = 'rain'
        elif 'sea' in sound_name:
            category = 'sea'
        elif 'sparkles' in sound_name:
            category = 'sparkles'
        elif 'background-music' in sound_name:
            category = 'background-music'
        
        if not category:
            return 0
            
        # Define all sounds in each category
        category_sounds = {
            'rain': ['rain00.mp3', 'rain01.mp3', 'rain02.mp3', 'rain03.mp3', 'rain04.mp3'],
            'sea': ['sea00.mp3', 'sea01.mp3', 'sea02.mp3', 'sea03.mp3', 'sea04.mp3'],
            'sparkles': ['sparkles00.mp3', 'sparkles01.mp3', 'sparkles02.mp3', 'sparkles03.mp3', 'sparkles04.mp3'],
            'background-music': ['background-music00.mp3', 'background-music01.mp3', 'background-music02.mp3', 'background-music03.mp3', 'background-music04.mp3']
        }
        
        # Check if user has listened to all sounds in this category
        required_sounds = category_sounds.get(category, [])
        listened_sounds = [sound for sound in listening_times.keys() if sound in required_sounds]
        
        # Award bonus only if just completed the category
        if len(listened_sounds) == len(required_sounds):
            # Check if this is the first time completing this category
            achievement_key = f"{category}_explorer"
            if achievement_key not in user_stats.get('category_completions', []):
                if 'category_completions' not in user_stats:
                    user_stats['category_completions'] = []
                user_stats['category_completions'].append(achievement_key)
                
                self.add_points(user_id, 50, f"Category completion: {category}", save_data=save_data)
                username = f'\033[35m{self.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")}\033[0m'
                logging.info(f"⭐ Category completion bonus: {username} completed {category} category ({colorize_points('+50 points')})")
                return 50
        
        return 0
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:

        users = []
        for user_id, stats in self.user_data.items():
            users.append({
                'user_id': user_id,
                'total_points': stats['total_points'],
                'level': stats['level'],
                'listening_time': stats['listening_time'],
                'achievements_count': len(stats['achievements']),
                'daily_streak': stats['daily_streak']
            })
        
        # Sort by points descending
        users.sort(key=lambda x: x['total_points'], reverse=True)
        return users[:limit]

    def get_user_rank(self, user_id: str) -> Optional[Dict]:

        leaderboard = self.get_leaderboard(1000)  # Get all users
        user_id = str(user_id)
        
        for index, user in enumerate(leaderboard):
            if user['user_id'] == user_id:
                return {
                    'rank': index + 1,
                    'total_users': len(leaderboard),
                    'user_stats': user
                }
        
        return None

# Global instance
cozy_gamification = CozyGamification()

