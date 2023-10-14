from discord import FFmpegPCMAudio
from discord.ext import commands
import asyncio

class RainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="rain", description="Play the sound of rain")
    async def _rain(self, ctx):
        await ctx.defer() 

        if ctx.author.voice is None:
            await ctx.respond("You need to be in a voice channel to use this command.")
            return

        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)

        await ctx.respond(f"{ctx.author.mention} has called {self.bot.user.mention} to play the sound of the rain 🌧️")

        audio_source = FFmpegPCMAudio(executable="ffmpeg", source="sounds/rain.mp3")
        ctx.voice_client.play(audio_source, after=lambda e: asyncio.run_coroutine_threadsafe(ctx.voice_client.disconnect(), self.bot.loop))

def setup(bot):
    bot.add_cog(RainCog(bot))
