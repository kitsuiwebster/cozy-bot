from discord.ext import commands
import json
import discord

class TopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Helper function to load voice channel time data from a file.
    def load_voice_time_data(self):
        try:
            with open('voice_time_data.json', 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}

    # Slash command to display the top server ranked by voice time.
    @commands.slash_command(name="top", description="Display the top servers!")
    async def _top(self, ctx):
        try:
            # Load the voice time data
            guild_voice_time = self.load_voice_time_data()

            # Sort the guilds by voice time (second element of tuple).
            sorted_guilds = sorted(guild_voice_time.items(), key=lambda x: x[1][1], reverse=True)

            # Create an embed object for the output
            embed = discord.Embed(title="Top Servers by time spent with CozyBot 🥇", description="", color=0x00ff00)
            
            # Add fields to the embed for each top server.
            for index, (guild_id, voice_time) in enumerate(sorted_guilds[:10], start=1):
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    # Format the time nicely
                    total_seconds = int(voice_time[1])
                    days, remainder = divmod(total_seconds, 86400)
                    hours, remainder = divmod(remainder, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_str = f"{days}d {hours}h {minutes}m {seconds}s"
                    embed.add_field(name=f"{index}. {guild.name}", value=time_str, inline=False)

            # Send the embed in the context.
            await ctx.respond(embed=embed)
        except Exception as e:
            # Send an error message if something goes wrong.
            await ctx.respond(f"An error occurred while executing the command: {e}")

# Function to add the TopCog to the bot.
def setup(bot):
    bot.add_cog(TopCog(bot))
