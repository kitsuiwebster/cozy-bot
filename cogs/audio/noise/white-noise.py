import discord
from discord import app_commands
from discord.ext import commands
from ..base_sound import BaseSoundCog

class WhiteNoiseCog(BaseSoundCog):
    def __init__(self, bot):
        sounds = ["white-noise00.mp3", "white-noise01.mp3", "white-noise02.mp3", "white-noise03.mp3", "white-noise04.mp3"]
        sound_labels = {
            "white-noise00.mp3": "🤍",
            "white-noise01.mp3": "🤍🌌🌕",
            "white-noise02.mp3": "🤍",
            "white-noise03.mp3": "🤍",
            "white-noise04.mp3": "🤍",
        }
        super().__init__(bot, "white-noise", sounds, sound_labels, "Play differnet types of white noises.🤍")

    @app_commands.command(name="white-noise", description="Play differnet types of white noises")
    async def noise_command(self, interaction: discord.Interaction):
        await self.play_sound_command(interaction, "Please select a white noise sound:")

async def setup(bot):
    await bot.add_cog(WhiteNoiseCog(bot))