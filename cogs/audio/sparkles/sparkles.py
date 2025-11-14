import discord
from discord import app_commands
from discord.ext import commands
from ..base_sound import BaseSoundCog

class SparklesCog(BaseSoundCog):
    def __init__(self, bot):
        sounds = ["sparkles00.mp3", "sparkles01.mp3", "sparkles02.mp3", "sparkles03.mp3", "sparkles04.mp3"]
        sound_labels = {
            "sparkles00.mp3": "✨🪄⭐",
            "sparkles01.mp3": "✨🌟💫",
            "sparkles02.mp3": "✨🪄💎",
            "sparkles03.mp3": "✨🌲🌙",
            "sparkles04.mp3": "✨🪄💫"
        }
        super().__init__(bot, "sparkles", sounds, sound_labels, "Play the sound of sparkles.✨")

    @app_commands.command(name="sparkles", description="Play the sound of sparkles")
    async def sparkles_command(self, interaction: discord.Interaction):
        await self.play_sound_command(interaction, "Please select a sparkles sound:")

async def setup(bot):
    await bot.add_cog(SparklesCog(bot))