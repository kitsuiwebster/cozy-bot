import discord
from discord import app_commands
from discord.ext import commands

class TotalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="total", description="Find out how many are currently soaking in coziness with me! 📊")
    async def total_command(self, interaction: discord.Interaction):
        total_people_with_bot = 0
        people_names = []

        for guild in self.bot.guilds:
            voice_state = guild.voice_client
            if voice_state and voice_state.channel:
                for member in voice_state.channel.members:
                    if member != self.bot.user:
                        total_people_with_bot += 1
                        people_names.append(member.display_name)

        # Cozy messages based on current listener count
        if total_people_with_bot == 0:
            message = "🌙 It's quiet right now... Join a voice channel and invite me for some cozy sounds!"
        elif total_people_with_bot == 1:
            message = f"🌧️ {people_names[0]} is currently enjoying some cozy vibes alone!"
        elif total_people_with_bot <= 5:
            message = f"✨ {total_people_with_bot} cozy listeners are currently relaxing: {', '.join(people_names[:3])}"
            if len(people_names) > 3:
                message += f" and {len(people_names) - 3} others"
        elif total_people_with_bot <= 10:
            message = f"🎵 {total_people_with_bot} people are currently in cozy mode! The relaxation is spreading!"
        else:
            message = f"🌊 Wow! {total_people_with_bot} people are currently soaking in coziness! What a peaceful community!"

        await interaction.response.send_message(message)

async def setup(bot):
    await bot.add_cog(TotalCog(bot))