import discord
from discord import app_commands
from discord.ext import commands
import json

class TopCog(commands.Cog):
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

    # Display guild rankings based on voice channel usage metrics
    @app_commands.command(name="top-servers", description="Display the top servers!")
    async def top_servers_command(self, interaction: discord.Interaction):
        try:
            # Retrieve voice channel usage statistics
            guild_voice_time = self.load_voice_time_data()

            # Sort guilds by accumulated voice time in descending order
            sorted_guilds = sorted(guild_voice_time.items(), key=lambda x: x[1][1], reverse=True)

            # Initialize Discord embed for ranking display
            embed = discord.Embed(title="Top Servers by time spent with CozyBot 🥇", description="", color=0x00ff00)
            
            # Populate embed with formatted guild rankings
            for index, (guild_id, voice_time) in enumerate(sorted_guilds[:10], start=1):
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    # Convert seconds to human-readable duration format
                    total_seconds = int(voice_time[1])
                    days, remainder = divmod(total_seconds, 86400)
                    hours, remainder = divmod(remainder, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_str = f"{days}d {hours}h {minutes}m {seconds}s"
                    embed.add_field(name=f"{index}. {guild.name}", value=time_str, inline=False)

            # Deliver formatted rankings response to user
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            # Handle command execution errors gracefully
            await interaction.response.send_message(f"An error occurred while executing the command: {e}", ephemeral=True)

# Register TopCog extension with bot instance
async def setup(bot):
    await bot.add_cog(TopCog(bot))