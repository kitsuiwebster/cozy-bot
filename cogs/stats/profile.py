import discord
from discord import app_commands
from discord.ext import commands
from .gamification import cozy_gamification

class ProfileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View your cozy profile and achievements 🏆")
    @app_commands.describe(user="User to view profile for (@username or just username)")
    async def profile_command(self, interaction: discord.Interaction, user: str = None):
        target_user = interaction.user
        
        # If user parameter provided, try to find the user
        if user:
            # Remove @ if present
            search_username = user.replace('@', '').strip()
            
            # Search for user by username in gamification data
            found_user = None
            for user_id, stats in cozy_gamification.user_data.items():
                try:
                    potential_user = await self.bot.fetch_user(int(user_id))
                    if potential_user and potential_user.name.lower() == search_username.lower():
                        found_user = potential_user
                        break
                except:
                    continue
            
            if found_user:
                target_user = found_user
            else:
                await interaction.response.send_message(f"❌ User '{search_username}' not found in the leaderboard.", ephemeral=True)
                return
        
        user_stats = cozy_gamification.get_user_stats(target_user.id)
        rank_info = cozy_gamification.get_user_rank(target_user.id)
        
        # Calculate listening time in readable format
        total_seconds = user_stats['listening_time']
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        
        # Get level progress
        level = user_stats['level']
        progress = user_stats['level_progress']
        
        # Create embed
        embed = discord.Embed(
            title=f"🌟 {target_user.name}'s Cozy Profile",
            color=0x00ff00  # Green
        )
        
        # Add profile picture
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        # Points and Level
        embed.add_field(
            name="✨ Cozy Points", 
            value=f"**{user_stats['total_points']:,}** points", 
            inline=True
        )
        
        embed.add_field(
            name="📈 Level", 
            value=f"**Level {level}** ({progress}%)", 
            inline=True
        )
        
        if rank_info:
            embed.add_field(
                name="🏆 Global Rank", 
                value=f"**#{rank_info['rank']}** / {rank_info['total_users']}", 
                inline=True
            )
        
        # Listening Stats
        embed.add_field(
            name="⏰ Listening Time", 
            value=f"**{hours}h {minutes}m**", 
            inline=True
        )
        
        embed.add_field(
            name="🎵 Sessions Joined", 
            value=f"**{user_stats['sessions_joined']}**", 
            inline=True
        )
        
        # Get current valid streak (0 if not active today)
        current_streak = cozy_gamification.get_current_streak(str(interaction.user.id))
        embed.add_field(
            name="🔥 Daily Streak", 
            value=f"**{current_streak} days**", 
            inline=True
        )
        
        # Favorite Sound
        if user_stats['favorite_sounds']:
            fav_sound = max(user_stats['favorite_sounds'], key=user_stats['favorite_sounds'].get)
            fav_count = user_stats['favorite_sounds'][fav_sound]
            
            # Map sound files to emojis
            sound_emojis = {
                "rain00.mp3": "🌧️💧⚡",
                "rain01.mp3": "🌧️🌿🌙",
                "rain02.mp3": "🌧️⛈️💨",
                "rain03.mp3": "🌧️🏠🔥",
                "rain04.mp3": "🌧️🚗⚡",
                "sea00.mp3": "🌊💧💦",
                "sea01.mp3": "🌊🕊️⛱️",
                "sea02.mp3": "🌊🏝️🌙",
                "sea03.mp3": "🌊⛵🕊️",
                "sea04.mp3": "🌊🤿🔱",
                "sparkles00.mp3": "✨🪄⭐",
                "sparkles01.mp3": "✨🌟💫",
                "sparkles02.mp3": "✨🪄💎",
                "sparkles03.mp3": "✨🌲🌙",
                "sparkles04.mp3": "✨🪄💫",
                "background-music00.mp3": "🎶🏛️🌙",
                "background-music01.mp3": "🎶🍃🌩️",
                "background-music02.mp3": "🎶🏺💦",
                "background-music03.mp3": "🎶🌸💦",
                "background-music04.mp3": "🎶🌿💦"
            }
            
            fav_display = sound_emojis.get(fav_sound, fav_sound)
            embed.add_field(
                name="🎶 Favorite Sound", 
                value=f"**{fav_display}** ({fav_count} times)", 
                inline=False
            )
        
        # Achievements
        if user_stats['achievements']:
            achievements_text = ' '.join(user_stats['achievements'][:10])  # First 10 achievements
            if len(user_stats['achievements']) > 10:
                achievements_text += f" +{len(user_stats['achievements']) - 10} more"
            embed.add_field(
                name=f"🏅 Achievements ({len(user_stats['achievements'])})", 
                value=achievements_text, 
                inline=False
            )
        else:
            embed.add_field(
                name="🏅 Achievements", 
                value="Start listening to earn achievements!", 
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="achievements", description="View all available achievements 🏅")
    async def achievements_command(self, interaction: discord.Interaction):
        user_stats = cozy_gamification.get_user_stats(interaction.user.id)
        earned_achievements = user_stats['achievements']
        
        # Create embed with top-servers style
        embed = discord.Embed(title="Achievements 🏅", description="", color=0x00ff00)
        
        # Level Achievements
        level_achievements = [
            ("🥉 Bronze", "Reach Level 5", user_stats['level'] >= 5),
            ("🥈 Silver", "Reach Level 10", user_stats['level'] >= 10),
            ("🥇 Gold", "Reach Level 15", user_stats['level'] >= 15),
            ("💎 Diamond", "Reach Level 25", user_stats['level'] >= 25),
            ("👑 Master", "Reach Level 50", user_stats['level'] >= 50)
        ]
        
        level_text = ""
        for achievement, description, earned in level_achievements:
            status = "✅" if earned else "🔒"
            level_text += f"{status} {achievement}\n    {description}\n"
        
        embed.add_field(name="📈 Level Achievements", value=level_text, inline=False)
        
        # Time Achievements
        hours = user_stats['listening_time'] / 3600
        time_achievements = [
            ("⏰ First Hour", "Listen for 1 hour total", hours >= 1),
            ("🕐 Dedicated Listener", "Listen for 10 hours total", hours >= 10),
            ("⏰ Time Master", "Listen for 50 hours total", hours >= 50),
            ("🕰️ Eternal Listener", "Listen for 100 hours total", hours >= 100),
            ("☯️ Time Lord", "Listen for 1000 hours total", hours >= 1000)
        ]
        
        time_text = ""
        for achievement, description, earned in time_achievements:
            status = "✅" if earned else "🔒"
            time_text += f"{status} {achievement}\n    {description}\n"
        
        embed.add_field(name="⏰ Time Achievements", value=time_text, inline=False)
        
        # Streak Achievements
        streak = user_stats['daily_streak']
        streak_achievements = [
            ("🔥 Week Warrior", "7 day streak", streak >= 7),
            ("📅 Monthly Master", "30 day streak", streak >= 30),
            ("💯 Streak Legend", "100 day streak", streak >= 100),
            ("🗓️ Year Champion", "365 day streak", streak >= 365)
        ]
        
        streak_text = ""
        for achievement, description, earned in streak_achievements:
            status = "✅" if earned else "🔒"
            streak_text += f"{status} {achievement}\n    {description}\n"
        
        embed.add_field(name="🔥 Streak Achievements", value=streak_text, inline=False)
        
        # Special Achievements
        special_achievements = [
            ("🌧️ Rain Master", "Play rain sounds 50+ times"),
            ("🌊 Sea Master", "Play sea sounds 50+ times"),
            ("✨ Sparkles Master", "Play sparkles sounds 50+ times"),
            ("🎵 Music Master", "Play background music 50+ times")
        ]
        
        special_text = ""
        for achievement, description in special_achievements:
            status = "✅" if achievement in earned_achievements else "🔒"
            special_text += f"{status} {achievement}\n    {description}\n"
        
        embed.add_field(name="🌟 Special Achievements", value=special_text, inline=False)
        
        total_possible = 18  # Update as we add more achievements
        total_earned = len(earned_achievements)
        embed.set_footer(text=f"Progress: {total_earned}/{total_possible} achievements unlocked")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(ProfileCog(bot))