import discord
from discord import app_commands
from discord.ext import commands

class CreditsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="credits", description="View credits for all sound creators")
    async def credits_command(self, interaction: discord.Interaction):
        """Display credits for all sound creators"""
        
        # Create informative embed
        embed = discord.Embed(
            title="🎵 CozyBot Credits",
            description="The credits of all creators of CozyBot's sounds are listed here:",
            color=0x00ff00  # Green color
        )
        
        # Add credits URL
        embed.add_field(
            name="📖 Full Credits List",
            value="[View all sound creators and attributions](https://kitsuiwebster.com/cozybot/credits)",
            inline=False
        )
        
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(CreditsCog(bot))