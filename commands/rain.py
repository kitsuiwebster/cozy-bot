import asyncio
from discord.ext import commands
from discord import FFmpegPCMAudio

class RainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def rain(self, ctx):
        # Deletes user's message

        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)

        # Plays the sound
        audio_source = FFmpegPCMAudio(executable="ffmpeg", source="sounds/rain.mp3")
        ctx.voice_client.play(audio_source, after=lambda e: asyncio.run_coroutine_threadsafe(ctx.voice_client.disconnect(), self.bot.loop))

async def setup(bot):
    await bot.add_cog(RainCog(bot))
