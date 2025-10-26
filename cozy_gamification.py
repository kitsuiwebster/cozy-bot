import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio

class CozyGamification:
    def __init__(self):
        self.data_file = 'data/cozy_points.json'
        self.user_data = self.load_user_data()
        
    def load_user_data(self) -> Dict:
        """Load user gamification data from persistent storage"""
        try:
            os.makedirs('data', exist_ok=True)
            with open(self.data_file, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}
    
    def save_user_data(self):
        """Save user gamification data to persistent storage"""
        try:
            os.makedirs('data', exist_ok=True)
            with open(self.data_file, 'w') as file:
                json.dump(self.user_data, file, indent=2)
        except Exception as e:
            print(f"Error saving cozy points data: {e}")
    
    def get_user_stats(self, user_id: str) -> Dict:
        """Get or create user statistics"""
        user_id = str(user_id)
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
                'level_progress': 0
            }
        return self.user_data[user_id]
    
    def add_points(self, user_id: str, points: int, reason: str = "Listening") -> Dict:
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
        
        if level_up:
            new_achievements.extend(self.check_level_achievements(new_level, user_stats))
        
        # Check other achievements
        new_achievements.extend(self.check_general_achievements(user_stats))
        
        self.save_user_data()
        
        return {
            'points_added': points,
            'total_points': user_stats['total_points'],
            'level_up': level_up,
            'new_level': new_level if level_up else None,
            'new_achievements': new_achievements,
            'reason': reason
        }
    
    def calculate_level(self, total_points: int) -> tuple:
        """Calculate user level and progress based on total points"""
        # Level progression: 100, 250, 500, 1000, 2000, 4000, etc.
        level = 1
        points_needed = 100
        
        while total_points >= points_needed:
            total_points -= points_needed
            level += 1
            points_needed = int(points_needed * 1.5)  # Exponential growth
        
        progress = (total_points / points_needed) * 100
        return level, round(progress, 1)
    
    def add_listening_time(self, user_id: str, seconds: float):
        """Add listening time and award points"""
        user_stats = self.get_user_stats(user_id)
        user_stats['listening_time'] += seconds
        
        # Award points: 1 point per minute
        points_to_add = int(seconds / 60)
        if points_to_add > 0:
            return self.add_points(user_id, points_to_add, "Listening time")
        return None
    
    def track_sound_preference(self, user_id: str, sound_name: str):
        """Track user's favorite sounds"""
        user_stats = self.get_user_stats(user_id)
        if sound_name not in user_stats['favorite_sounds']:
            user_stats['favorite_sounds'][sound_name] = 0
        user_stats['favorite_sounds'][sound_name] += 1
        self.save_user_data()
    
    def join_session(self, user_id: str):
        """Track when user joins a listening session"""
        user_stats = self.get_user_stats(user_id)
        user_stats['sessions_joined'] += 1
        
        # Update daily streak
        today = datetime.now().strftime('%Y-%m-%d')
        last_active = user_stats.get('last_active_date')
        
        if last_active != today:
            if last_active and self.is_consecutive_day(last_active, today):
                user_stats['daily_streak'] += 1
            else:
                user_stats['daily_streak'] = 1
            user_stats['last_active_date'] = today
        
        # Award session join points
        result = self.add_points(user_id, 5, "Joining session")
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