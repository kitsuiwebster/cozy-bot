import discord
from discord import app_commands
from discord.ext import commands
import json
from .gamification import cozy_gamification

class TopsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Load voice channel usage statistics from persistent storage
    def load_voice_time_data(self):
        data_file = 'data/voice_time_data.json'
        try:
            with open(data_file, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}

    # Load server names cache from JSON file
    def load_servernames_data(self):
        data_file = 'data/servernames.json'
        try:
            with open(data_file, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}

    @app_commands.command(name="top-servers", description="Display the top servers")
    async def top_servers_command(self, interaction: discord.Interaction):
        try:
            # Retrieve voice channel usage statistics and server names
            guild_voice_time = self.load_voice_time_data()
            servernames_data = self.load_servernames_data()

            # Sort guilds by accumulated voice time in descending order
            sorted_guilds = sorted(guild_voice_time.items(), key=lambda x: x[1][1], reverse=True)

            # Initialize Discord embed for ranking display
            embed = discord.Embed(title="Top Servers by time spent with CozyBot 🥇", description="", color=0x00ff00)
            
            # Populate embed with formatted guild rankings
            for index, (guild_id, voice_time) in enumerate(sorted_guilds[:10], start=1):
                guild = self.bot.get_guild(int(guild_id))
                
                # Get server name from cache or current guild, fallback to "Old Server"
                if guild:
                    server_name = guild.name
                else:
                    server_info = servernames_data.get(guild_id)
                    if isinstance(server_info, dict):
                        server_name = server_info.get('name', "Old Server")
                    else:
                        server_name = "Old Server"
                
                # Convert seconds to human-readable duration format
                total_seconds = int(voice_time[1])
                days, remainder = divmod(total_seconds, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_str = f"{days}d {hours}h {minutes}m {seconds}s"
                embed.add_field(name=f"{index}. {server_name}", value=time_str, inline=False)

            # Deliver formatted rankings response to user
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            # Handle command execution errors gracefully
            await interaction.response.send_message(f"An error occurred while executing the command: {e}", ephemeral=True)

    @app_commands.command(name="top-users", description="View the top users")
    async def top_users_command(self, interaction: discord.Interaction):
        leaderboard = cozy_gamification.get_leaderboard(10)
        
        if not leaderboard:
            await interaction.response.send_message("No cozy listeners yet! Be the first to start earning points! 🎵")
            return
        
        # Create embed with top-servers style
        embed = discord.Embed(title="Top Users by cozy points 🥇", description="", color=0x00ff00)
        
        # Format leaderboard like top-servers  
        for i, user_data in enumerate(leaderboard, start=1):
            user_id = user_data['user_id']
            
            # Get display name from cache first
            display_name = None
            if user_id in cozy_gamification.usernames:
                cached_info = cozy_gamification.usernames[user_id]
                if isinstance(cached_info, dict):
                    display_name = cached_info.get('display_name')
            
            # Fallback to fetching user if no cached display name
            if not display_name:
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    display_name = user.global_name or user.name if user else f"User {user_id[:8]}"
                except:
                    try:
                        user = self.bot.get_user(int(user_id))
                        display_name = user.global_name or user.name if user else f"User {user_id[:8]}"
                    except:
                        display_name = f"User {user_id[:8]}"
            
            user_info = f"{user_data['total_points']:,} points"
            embed.add_field(name=f"{i}. {display_name}", value=user_info, inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="top-sounds", description="View the most listened sounds")
    async def top_sounds_command(self, interaction: discord.Interaction):
        try:
            # Load cozy points data to aggregate sound listening times
            user_data = None
            
            # Try to load encrypted data first
            try:
                from utils.encryption import encryption
                user_data = encryption.load_encrypted_json('data/cozy_points.json')
            except ImportError:
                pass
            
            # Fallback to standard JSON if encryption not available
            if not user_data:
                data_file = 'data/cozy_points.json'
                try:
                    with open(data_file, 'r') as file:
                        user_data = json.load(file)
                except FileNotFoundError:
                    await interaction.response.send_message("No listening data found yet! Start playing some sounds! 🎵")
                    return
                    
            if not user_data:
                await interaction.response.send_message("No listening data found yet! Start playing some sounds! 🎵")
                return
            
            # Aggregate sound data across all users
            sound_aggregates = {}
            
            for user_id, user_stats in user_data.items():
                listening_times = user_stats.get('listening_time_by_sound', {})
                
                for sound_name, sound_data in listening_times.items():
                    if sound_name not in sound_aggregates:
                        sound_aggregates[sound_name] = {
                            'total_time': 0.0,
                            'total_sessions': 0,
                            'unique_listeners': set()
                        }
                    
                    sound_aggregates[sound_name]['total_time'] += sound_data['total_time']
                    sound_aggregates[sound_name]['total_sessions'] += sound_data['session_count']
                    sound_aggregates[sound_name]['unique_listeners'].add(user_id)
            
            if not sound_aggregates:
                await interaction.response.send_message("No sound listening data yet! Start playing some cozy sounds! 🎵")
                return
            
            # Convert to list and sort by total time
            sounds_list = []
            for sound_name, data in sound_aggregates.items():
                display_name = cozy_gamification.get_sound_display_name(sound_name)
                total_time = data['total_time']
                unique_listeners = len(data['unique_listeners'])
                
                sounds_list.append({
                    'display_name': display_name,
                    'total_time': total_time,
                    'unique_listeners': unique_listeners
                })
            
            # Sort by total time descending and take top 10
            sounds_list.sort(key=lambda x: x['total_time'], reverse=True)
            top_sounds = sounds_list[:10]
            
            # Create embed with same style as other tops
            embed = discord.Embed(title="Top Sounds by listening time 🎵", description="", color=0x00ff00)
            
            # Format like top-servers
            for i, sound_data in enumerate(top_sounds, start=1):
                # Convert seconds to human-readable duration format
                total_seconds = int(sound_data['total_time'])
                days, remainder = divmod(total_seconds, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if days > 0:
                    time_str = f"{days}d {hours}h {minutes}m"
                elif hours > 0:
                    time_str = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    time_str = f"{minutes}m {seconds}s"
                else:
                    time_str = f"{seconds}s"
                
                listeners_info = f"{time_str} • {sound_data['unique_listeners']} listeners"
                embed.add_field(name=f"{i}. {sound_data['display_name']}", value=listeners_info, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"An error occurred while executing the command: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(TopsCog(bot))