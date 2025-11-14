import discord
from discord import app_commands
from discord.ext import commands

class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stats", description="View CozyBot statistics and leaderboards")
    async def stats(self, interaction: discord.Interaction):
        # Create embed with stats website info
        embed = discord.Embed(
            title="CozyBot Statistics",
            description="Access CozyBot statistics",
            color=0x00ff00,  # Green
            url="https://kitsuiwebster.com/cozybot"
        )
        
        embed.add_field(
            name="Website",
            value="[**kitsuiwebster.com/cozybot**](https://kitsuiwebster.com/cozybot)",
            inline=False
        )
        
        embed.add_field(
            name="What you'll find:",
            value="**Top Users** - See who has the most cozy points\n"
                  "**Top Servers** - Most active Discord servers\n"
                  "**Top Sounds** - Most listened ambient sounds\n"
                  "**Real-time Statistics** - Live data updated continuously",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(StatsCog(bot))