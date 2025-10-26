import discord
from discord import app_commands
from discord.ext import commands

class TotalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="total", description="Find out how many are currently soaking in coziness with me!")
    async def total_command(self, interaction: discord.Interaction):
        total_people_with_bot = 0
        people_names = []

        for guild in self.bot.guilds:
            voice_state = guild.voice_client
            if voice_state and voice_state.channel:
                for member in voice_state.channel.members:
                    if not member.bot:  # Filter out bot accounts from user count
                        people_names.append(member.display_name)
                        total_people_with_bot += 1

        if total_people_with_bot == 1:
            message = f"Right now, 1 soul is wrapped in the warmth of my cozy ambiance."
        elif total_people_with_bot > 1:
            message = f"Right now, {total_people_with_bot} souls are wrapped in the warmth of my cozy ambiance."
        else:
            message = "No one is currently with me in a voice channel... Maybe it's time for you to call me? 👀"

        await interaction.response.send_message(message)  # Deliver user count response

async def setup(bot):
    await bot.add_cog(TotalCog(bot))