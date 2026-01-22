import discord
from discord import app_commands
from discord.ext import commands
from ..base_sound import BaseSoundCog
from ..sound_mappings import SOUND_LABELS

# Cog for playing background music
class BackgroundMusicCog(BaseSoundCog):
    def __init__(self, bot):
        sounds = ["background-music00.mp3", "background-music01.mp3", "background-music02.mp3", "background-music03.mp3", "background-music04.mp3"]
        sound_labels = {sound: SOUND_LABELS[sound] for sound in sounds}
        super().__init__(bot, "background-music", sounds, sound_labels, "Play some music in the background.🎶")

    @app_commands.command(name="music", description="Play some music in the background")
    async def background_music_command(self, interaction: discord.Interaction):
        await self.play_sound_command(interaction, "Please select background music:")

async def setup(bot):
    await bot.add_cog(BackgroundMusicCog(bot))