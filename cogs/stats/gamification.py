import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
import fcntl
import logging
import traceback

# Import encryption utilities
try:
    from utils.encryption import encryption
    ENCRYPTION_ENABLED = True
    logging.info("🔒 Encryption enabled for data storage")
except ImportError:
    ENCRYPTION_ENABLED = False
    logging.warning("⚡ Encryption disabled - install cryptography for data encryption")

def colorize_points(text):
    """Colorize point values in green"""
    return f'\033[32m{text}\033[0m'

def colorize_duration(text):
    """Colorize duration values in blue"""
    return f'\033[94m{text}\033[0m'

class CozyGamification:
    def __init__(self):
        self.data_file = 'data/cozy_points.json'
        self.usernames_file = 'data/usernames.json'
        self.servernames_file = 'data/servernames.json'
        self.user_data = self.load_user_data()
        self.usernames = self.load_usernames()
        self.servernames = self.load_servernames()
        
        # Track changes since last save for logging
        self.changes_since_save = {
            'user_listening_time': {},  # user_id: added_seconds
            'user_sound_time': {},      # user_id: {sound_name: added_seconds}
            'user_points': {},          # user_id: added_points
            'user_points_breakdown': {} # user_id: [{'reason': str, 'points': int}]
        }
        
        # Clean corrupted data on startup
        self.clean_corrupted_data()
        
    def load_user_data(self) -> Dict:
        """Load user gamification data from persistent storage with validation"""
        try:
            os.makedirs('data', exist_ok=True)
            
            if ENCRYPTION_ENABLED:
                # Try to load encrypted data first
                data = encryption.load_encrypted_json(self.data_file)
                if data:
                    logging.info('🔒 Loaded encrypted gamification data')
                    return data
                
                # If no encrypted data, try to migrate from unencrypted
                try:
                    with open(self.data_file, 'r') as file:
                        data = json.load(file)
                        if isinstance(data, dict):
                            logging.info('👉 Migrating unencrypted data to encrypted format...')
                            self._migrate_to_encrypted(data)
                            return data
                except FileNotFoundError:
                    logging.info('❌ No existing unencrypted data found, starting fresh')
                    return {}
            else:
                # Standard JSON loading
                with open(self.data_file, 'r') as file:
                    data = json.load(file)
                    if isinstance(data, dict):
                        return data
                    else:
                        logging.warning('❌ Invalid gamification data structure, starting fresh')
                        return {}
                        
        except FileNotFoundError:
            logging.info('❌ No existing gamification data found, starting fresh')
            return {}
        except json.JSONDecodeError as e:
            logging.error(f'❌ Corrupted gamification data file: {e}, starting fresh')
            # Try to backup corrupted file
            try:
                backup_file = self.data_file + f'.corrupted.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
                os.rename(self.data_file, backup_file)
                logging.info(f'❌ Corrupted file backed up as: {backup_file}')
            except Exception:
                pass
            return {}
        except Exception as e:
            logging.error(f'❌ Error loading gamification data: {e}')
            return {}
    
    def _migrate_to_encrypted(self, data: Dict):
        """Migrate unencrypted data to encrypted format"""
        try:
            # Save as encrypted
            encryption.save_encrypted_json(data, self.data_file)
            # Remove old unencrypted file
            os.remove(self.data_file)
            logging.info('✅ Data migration to encrypted format completed')
        except Exception as e:
            logging.error(f'❌ Failed to migrate data to encrypted format: {e}')
    
    def load_usernames(self) -> Dict:
        """Load username cache from persistent storage"""
        try:
            if ENCRYPTION_ENABLED:
                # Try to load encrypted usernames first
                data = encryption.load_encrypted_json(self.usernames_file)
                if data:
                    logging.info('🔒 Loaded encrypted usernames cache')
                    return data
                
                # If no encrypted data, try to migrate from unencrypted
                try:
                    with open(self.usernames_file, 'r') as file:
                        data = json.load(file)
                        if isinstance(data, dict):
                            logging.info('👉 Migrating usernames to encrypted format...')
                            self._migrate_usernames_to_encrypted(data)
                            return data
                except FileNotFoundError:
                    pass
            else:
                # Standard JSON loading
                with open(self.usernames_file, 'r') as file:
                    return json.load(file)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}
        except Exception as e:
            logging.error(f'❌ Error loading usernames: {e}')
            return {}
    
    def _migrate_usernames_to_encrypted(self, data: Dict):
        """Migrate unencrypted usernames to encrypted format"""
        try:
            # Save as encrypted
            encryption.save_encrypted_json(data, self.usernames_file)
            # Remove old unencrypted file
            os.remove(self.usernames_file)
            logging.info('✅ Usernames migration to encrypted format completed')
        except Exception as e:
            logging.error(f'❌ Failed to migrate usernames to encrypted format: {e}')
    
    def save_usernames(self):
        """Save username cache to persistent storage"""
        try:
            os.makedirs('data', exist_ok=True)
            if ENCRYPTION_ENABLED:
                # Save encrypted usernames
                encryption.save_encrypted_json(self.usernames, self.usernames_file)
            else:
                # Standard JSON saving
                with open(self.usernames_file, 'w') as file:
                    json.dump(self.usernames, file, indent=2)
        except Exception as e:
            logging.error(f'❌ Failed to save usernames: {e}')
    
    def load_servernames(self) -> Dict:
        """Load server names cache from persistent storage"""
        try:
            with open(self.servernames_file, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}
    
    def save_servernames(self):
        """Save server names cache to persistent storage"""
        try:
            os.makedirs('data', exist_ok=True)
            with open(self.servernames_file, 'w') as file:
                json.dump(self.servernames, file, indent=2)
        except Exception as e:
            logging.error(f'❌ Failed to save server names: {e}')
    
    def update_servername(self, guild_id: str, guild_name: str):
        """Update server name in cache"""
        self.servernames[str(guild_id)] = {
            'name': guild_name,
            'last_updated': datetime.now().isoformat()
        }
        self.save_servernames()
    
    def update_username(self, user_id: str, username: str, display_name: str = None):
        """Update username and display name in cache"""
        user_id = str(user_id)
        self.usernames[user_id] = {
            'username': username,
            'display_name': display_name or username,
            'last_updated': datetime.now().isoformat()
        }
        self.save_usernames()
    
    def save_user_data(self, force_detailed_log=False):
        """Save user gamification data to persistent storage with atomic writes"""
        # Ensure data directory exists
        os.makedirs('data', exist_ok=True)
        
        try:
            if ENCRYPTION_ENABLED:
                # Save encrypted data
                encryption.save_encrypted_json(self.user_data, self.data_file)
            else:
                # Standard JSON saving with atomic writes
                temp_file = self.data_file + '.tmp'
                with open(temp_file, 'w') as file:
                    fcntl.flock(file.fileno(), fcntl.LOCK_EX)
                    json.dump(self.user_data, file, indent=2)
                    file.flush()
                    os.fsync(file.fileno())
                
                # Atomic rename to final file
                os.rename(temp_file, self.data_file)
            
            # Log changes since last save (or force detailed log for hourly backup)
            from main import format_duration
            
            has_changes = any(self.changes_since_save['user_listening_time']) or any(self.changes_since_save['user_sound_time']) or any(self.changes_since_save['user_points'])
            
            if has_changes or force_detailed_log:
                save_type = "PERIODIC SAVE" if force_detailed_log else "EVENT SAVE"
                logging.info(f"✅️ {save_type} - Changes since last save:")
                
                # Log user changes
                for user_id in set(list(self.changes_since_save['user_listening_time'].keys()) + 
                                 list(self.changes_since_save['user_sound_time'].keys()) + 
                                 list(self.changes_since_save['user_points'].keys())):
                    
                    username = f'\033[35m{self.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")}\033[0m'
                    
                    # Total listening time for this user
                    if user_id in self.changes_since_save['user_listening_time']:
                        total_time = self.changes_since_save['user_listening_time'][user_id]
                        if total_time > 0:
                            logging.info(f"  👉 {colorize_duration(f'+{format_duration(total_time)}')} for {username}")
                    
                    # Points breakdown for this user
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
                    
                    # Sound-specific time for this user - SAFE ACCESS
                    if (isinstance(self.changes_since_save['user_sound_time'], dict) and 
                        user_id in self.changes_since_save['user_sound_time']):
                        user_sound_data = self.changes_since_save['user_sound_time'][user_id]
                        if isinstance(user_sound_data, dict):
                            for sound_name, sound_time in user_sound_data.items():
                                if isinstance(sound_time, (int, float)) and sound_time > 0:
                                    logging.info(f"  👉 {colorize_duration(f'+{format_duration(sound_time)}')} of {sound_name} for {username}")
                
                # Reset tracking for next period
                self.changes_since_save = {
                    'user_listening_time': {},
                    'user_sound_time': {},
                    'user_points': {},
                    'user_points_breakdown': {}
                }
            else:
                logging.debug(f"🚫 EVENT SAVE - No changes since last save")
            
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_file):
                os.remove(temp_file)
            logging.error(f'❌ Failed to save gamification data: {e}\n{traceback.format_exc()}')
    
    def get_user_stats(self, user_id: str) -> Dict:
        """Get or create user statistics"""
        user_id = str(user_id)
        if self.user_data is None:
            self.user_data = {}
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                'total_points': 0,
                'listening_time': 0.0,  # seconds
                'sessions_joined': 0,
                'favorite_sounds': {},
                'achievements': [],
                'daily_streak': 0,
                'last_active_date': None,
                'level': 1,
                'level_progress': 0,
            }
        return self.user_data[user_id]
    
    def add_points(self, user_id: str, points: int, reason: str = "Listening", save_data: bool = True) -> Dict:
        """Add points to user and handle level progression"""
        user_stats = self.get_user_stats(user_id)
        user_stats['total_points'] += points
        
        # Calculate level and progress
        old_level = user_stats['level']
        new_level, progress = self.calculate_level(user_stats['total_points'])
        user_stats['level'] = new_level
        user_stats['level_progress'] = progress
        
        # Check for level up achievements
        level_up = new_level > old_level
        new_achievements = []
        level_bonus_points = 0
        
        # Handle level-ups with proper cascade handling
        current_level = old_level
        total_level_bonus_points = 0
        
        while level_up:
            current_level += 1
            single_level_bonus = current_level * 10
            total_level_bonus_points += single_level_bonus
            user_stats['total_points'] += single_level_bonus
            
            username = f'\033[35m{self.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")}\033[0m'
            logging.info(f"⭐ Level bonus: {username} reached level {current_level} ({colorize_points(f'+{single_level_bonus} points')})")
            
            # Check for level achievements for THIS level
            level_achievements = self.check_level_achievements(current_level, user_stats)
            if level_achievements:
                logging.info(f"🏆 Level achievement: {username} unlocked {', '.join(level_achievements)}")
            new_achievements.extend(level_achievements)
            
            # Check if bonus points caused ANOTHER level up
            new_level, progress = self.calculate_level(user_stats['total_points'])
            user_stats['level'] = new_level
            user_stats['level_progress'] = progress
            
            # Continue loop if we leveled up again
            level_up = new_level > current_level
            
        # Update final level bonus points for return value
        level_bonus_points = total_level_bonus_points
        
        # Check other achievements
        new_achievements.extend(self.check_general_achievements(user_stats))
        
        # Award bonus points for achievements (+100 points per achievement)
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
        """Calculate user level and progress based on total points"""
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
        """Add listening time and award points"""
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
    
    def track_sound_start(self, user_id: str, sound_name: str):
        """Track when user starts listening to a sound"""
        user_stats = self.get_user_stats(user_id)

        # Note: finalize_current_sound is now handled at the calling site to control timing

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

        self.save_user_data()
    
    def reset_consecutive_time_for_guild(self, guild_id: str, users_in_vocal: List[str]):
        """Reset consecutive time for all users in the same vocal when sound changes"""
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
        """Finalize current sound listening session and add time"""
        user_stats = self.get_user_stats(user_id)
        current_sound = user_stats.get('current_sound')
        
        if current_sound and isinstance(current_sound, dict) and 'start_time' in current_sound:
            try:
                start_time = datetime.fromisoformat(current_sound['start_time'])
                duration = (datetime.now() - start_time).total_seconds()
                
                # Cap duration to 30 minutes to prevent corrupted data
                max_duration = 30 * 60  # 30 minutes in seconds
                if duration > max_duration:
                    duration = max_duration
                
                sound_name = current_sound['name']
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
                user_stats['current_sound'] = None
                
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
                
                # Award points for listening time
                points_added = int(duration / 60)
                bonus_points = 0
                
                # Check for loyalty bonuses (30min=+50pts, 1h=+100pts, 12h=+500pts)
                # Use TOTAL CONSECUTIVE session time (including current duration)
                consecutive_sound_time = user_stats['listening_time_by_sound'][sound_name]['consecutive_time']
                consecutive_minutes = consecutive_sound_time / 60
                
                # Calculate loyalty bonuses based on consecutive time milestones
                loyalty_bonus = 0
                if consecutive_minutes >= 720:  # 12 hours
                    loyalty_bonus = 500
                    reason = f"12h loyalty bonus on {sound_name}"
                    self.add_points(user_id, 500, reason, save_data=False)
                elif consecutive_minutes >= 60:  # 1 hour
                    loyalty_bonus = 100
                    reason = f"1h loyalty bonus on {sound_name}"
                    self.add_points(user_id, 100, reason, save_data=False)
                elif consecutive_minutes >= 30:  # 30 minutes
                    loyalty_bonus = 50
                    reason = f"30min loyalty bonus on {sound_name}"
                    self.add_points(user_id, 50, reason, save_data=False)
                
                if points_added > 0:
                    self.add_points(user_id, points_added, f"Listening to {sound_name}", save_data=False)
                
                # Check for category completion bonus
                category_bonus = self.check_category_completion_bonus(user_id, sound_name, save_data=False)
                bonus_points = loyalty_bonus + category_bonus
                
                # Log the sound tracking addition
                from main import format_duration
                duration_str = format_duration(duration)
                username = f'\033[35m{self.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")}\033[0m'
                total_points = points_added + bonus_points
                point_word = "points" if total_points != 1 else "point"
                points_str = f" ({colorize_points(f'+{total_points} {point_word}')})" if total_points > 0 else ""
                bonus_str = f" [{colorize_points(f'+{bonus_points} bonus')}]" if bonus_points > 0 else ""
                logging.info(f"👉 {colorize_duration(f'+{duration_str}')} of {sound_name} for {username}{points_str}{bonus_str}")
                
                # Single save at the end to avoid multiple EVENT SAVE logs
                self.save_user_data()
                
            except Exception as e:
                logging.error(f'❌ Error finalizing sound session: {e}\n{traceback.format_exc()}')
                user_stats['current_sound'] = None
    
    def track_sound_preference(self, user_id: str, sound_name: str):
        """Track user's favorite sounds (legacy method, redirects to new system)"""
        self.track_sound_start(user_id, sound_name)
    
    def get_sound_display_name(self, sound_filename: str) -> str:
        """Convert sound filename to emoji display name"""
        sound_mapping = {
            # Rain sounds (from actual Discord buttons)
            'rain00.mp3': '🌧️💧⚡',
            'rain01.mp3': '🌧️🌿🌙',
            'rain02.mp3': '🌧️⛈️💨',
            'rain03.mp3': '🌧️🏠🔥',
            'rain04.mp3': '🌧️🚗⚡',
            'rain05.mp3': '🌧️🌧️🌧️',
            'rain06.mp3': '🌧️🐦🌿',
            'rain07.mp3': '🌧️🌧️🌧️',
            'rain08.mp3': '🌧️🔥⛺',
            'rain09.mp3': '🌧️🧚🏻‍♀️🌲',
            # Sea sounds (from actual Discord buttons)
            'sea00.mp3': '🌊💧💦',
            'sea01.mp3': '🌊🕊️⛱️',
            'sea02.mp3': '🌊🏝️🌙',
            'sea03.mp3': '🌊⛵🕊️',
            'sea04.mp3': '🌊🤿🔱',
            # Sparkles sounds (from actual Discord buttons)
            'sparkles00.mp3': '✨🪄⭐',
            'sparkles01.mp3': '✨🌟💫',
            'sparkles02.mp3': '✨🪄💎',
            'sparkles03.mp3': '✨🌲🌙',
            'sparkles04.mp3': '✨🪄💫',
            # Background music (from actual Discord buttons)
            'background-music00.mp3': '🎶🏛️🌙',
            'background-music01.mp3': '🎶🍃🌩️',
            'background-music02.mp3': '🎶🏺💦',
            'background-music03.mp3': '🎶🌸💦',
            'background-music04.mp3': '🎶🌿💦',
            # White noise sounds (from actual Discord buttons)
            'white-noise00.mp3': '🤍⏳🔜',
            'white-noise01.mp3': '🤍🌌🌕',
            'white-noise02.mp3': '🤍⏳🔜',
            'white-noise03.mp3': '🤍⏳🔜',
            'white-noise04.mp3': '🤍⏳🔜'
        }
        return sound_mapping.get(sound_filename, sound_filename)
    
    def get_user_favorite_sound(self, user_id: str) -> str:
        """Get user's most listened sound by time with emoji display"""
        user_stats = self.get_user_stats(user_id)
        listening_times = user_stats.get('listening_time_by_sound', {})
        
        if not listening_times:
            return None
            
        # Find sound with most time
        favorite = max(listening_times.items(), key=lambda x: x[1]['total_time'])
        if favorite[1]['total_time'] > 0:
            return self.get_sound_display_name(favorite[0])
        return None
    
    def join_session(self, user_id: str, username: str = None, force_bonus: bool = False):
        """Track when user joins a listening session"""
        user_stats = self.get_user_stats(user_id)
        
        # Check for recent join to prevent duplicate points from reconnections
        last_join_time = user_stats.get('last_join_time')
        current_time = datetime.now()
        
        # Prevent duplicate join points within 2 minutes (120 seconds)
        award_join_points = True
        if not force_bonus and last_join_time:
            try:
                last_join = datetime.fromisoformat(last_join_time)
                time_since_last_join = (current_time - last_join).total_seconds()
                if time_since_last_join < 120:  # Less than 2 minutes
                    award_join_points = False
            except Exception:
                # Invalid timestamp, reset and award points
                award_join_points = True
        
        # Reset consecutive time for all sounds when user joins a new session
        if 'listening_time_by_sound' in user_stats:
            for sound_name in user_stats['listening_time_by_sound']:
                if 'consecutive_time' not in user_stats['listening_time_by_sound'][sound_name]:
                    user_stats['listening_time_by_sound'][sound_name]['consecutive_time'] = 0.0
                user_stats['listening_time_by_sound'][sound_name]['consecutive_time'] = 0.0
        
        user_stats['sessions_joined'] += 1
        user_stats['last_join_time'] = current_time.isoformat()
        
        # Update username cache if provided
        if username:
            # username is actually the display_name here, we need both
            self.update_username(user_id, username, username)
        
        # Update daily streak
        today = datetime.now().strftime('%Y-%m-%d')
        last_active = user_stats.get('last_active_date')
        
        if last_active != today:
            if last_active and self.is_consecutive_day(last_active, today):
                user_stats['daily_streak'] += 1
            else:
                user_stats['daily_streak'] = 1
            user_stats['last_active_date'] = today
        
        # Award session join points only if not a recent duplicate
        result = None
        if award_join_points:
            result = self.add_points(user_id, 5, "Joining session")
        else:
            # Return a valid dict even with 0 points to maintain consistency
            result = {
                'points_added': 0,
                'total_points': user_stats['total_points'],
                'level_up': False,
                'new_level': None,
                'new_achievements': [],
                'reason': "Joining session (duplicate prevention)"
            }
        
        self.save_user_data()
        return result
    
    def is_consecutive_day(self, last_date: str, current_date: str) -> bool:
        """Check if current date is consecutive to last active date"""
        try:
            last = datetime.strptime(last_date, '%Y-%m-%d')
            current = datetime.strptime(current_date, '%Y-%m-%d')
            return (current - last).days == 1
        except:
            return False
    
    def get_current_streak(self, user_id: str) -> int:
        """Get the current valid streak for a user"""
        user_stats = self.get_user_stats(user_id)
        today = datetime.now().strftime('%Y-%m-%d')
        last_active = user_stats.get('last_active_date')
        
        # If last active was yesterday or today, return stored streak
        if last_active:
            try:
                last = datetime.strptime(last_active, '%Y-%m-%d')
                current = datetime.strptime(today, '%Y-%m-%d')
                days_diff = (current - last).days
                
                # If active today or yesterday, streak is still valid
                if days_diff <= 1:
                    return user_stats.get('daily_streak', 0)
            except:
                pass
        
        # Only reset streak to 0 if more than 1 day inactive
        return 0
    
    def calculate_streak_bonus(self, user_id: str, listening_duration_minutes: float) -> int:
        """Calculate streak bonus points based on current streak and listening time"""
        current_streak = self.get_current_streak(user_id)
        if current_streak <= 0:
            return 0
        
        # +[streak days] points every 10 minutes of listening
        ten_minute_periods = int(listening_duration_minutes / 10)
        if ten_minute_periods > 0:
            return current_streak * ten_minute_periods
        
        return 0
    
    def check_level_achievements(self, level: int, user_stats: Dict) -> List[str]:
        """Check for level-based achievements"""
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
        """Clean corrupted data structures on startup"""
        cleaned_count = 0
        
        # Clean user_data
        for user_id, stats in list(self.user_data.items()):
            if not isinstance(stats, dict):
                logging.warning(f"⚠️ Removing corrupted user data for {user_id} (type: {type(stats)})")
                del self.user_data[user_id]
                cleaned_count += 1
                continue
                
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
        """Check for general achievements based on stats"""
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
        
        # Sound preference achievements
        fav_sounds = user_stats['favorite_sounds']
        if fav_sounds:
            sound_achievements = {
                "🌧️ Rain Master": "rain",
                "🌊 Sea Master": "sea", 
                "✨ Sparkles Master": "sparkles",
                "🎵 Music Master": "background-music"
            }
            
            for achievement, sound_type in sound_achievements.items():
                if achievement not in current_achievements:
                    sound_count = sum(count for sound, count in fav_sounds.items() if sound_type in sound.lower())
                    if sound_count >= 50:
                        user_stats['achievements'].append(achievement)
                        achievements.append(achievement)
        
        return achievements
    
    def check_category_completion_bonus(self, user_id: str, sound_name: str, save_data: bool = True) -> int:
        """Check if user completed a sound category and award bonus"""
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
        """Get top users leaderboard"""
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
    
    def get_user_rank(self, user_id: str) -> Dict:
        """Get user's rank and position in leaderboard"""
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

