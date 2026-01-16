import discord
from discord import app_commands
from discord.ext import commands
from ..base_sound import BaseSoundCog
from ..sound_mappings import SOUND_LABELS

# Cog for playing rain sounds
class RainCog(BaseSoundCog):
    def __init__(self, bot):
        sounds = ["rain00.mp3", "rain01.mp3", "rain02.mp3", "rain03.mp3", "rain04.mp3", "rain05.mp3", "rain06.mp3", "rain07.mp3", "rain08.mp3", "rain09.mp3"]
        sound_labels = {sound: SOUND_LABELS[sound] for sound in sounds}
        super().__init__(bot, "rain", sounds, sound_labels, "Play the sound of rain.🌧️")

    @app_commands.command(name="rain", description="Play the sound of rain")
    async def rain_command(self, interaction: discord.Interaction):
        await self.play_sound_command(interaction, "Please select a rain sound:")

async def setup(bot):
    await bot.add_cog(RainCog(bot))