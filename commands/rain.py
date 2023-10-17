from discord import FFmpegPCMAudio, ButtonStyle
from discord.ext import commands
from discord.ui import Button, View

class RainView(View):
    def __init__(self, rain_sounds, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        for i, sound in enumerate(rain_sounds):
            button = Button(style=ButtonStyle.primary, label=f"Rain Sound {i+1}", custom_id=sound)
            button.callback = self.on_button_click
            self.add_item(button)

    async def on_button_click(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the user who initiated the interaction can use these buttons.", ephemeral=True)
            return
        interaction.view.bot.dispatch("button_click", interaction)

class RainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rain_sounds = ["rain00.mp3", "rain01.mp3", "fart00.mp3"]

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

        view = RainView(self.rain_sounds, ctx.author.id)
        view.bot = self.bot
        await ctx.respond("Please select a rain sound:", view=view)

    @commands.Cog.listener()
    async def on_button_click(self, interaction):
        if interaction.custom_id in self.rain_sounds:
            await interaction.response.defer()
            await interaction.response.send_message(f"{interaction.user.mention} has called {self.bot.user.mention} to play the sound of the rain 🌧️")

            audio_source = FFmpegPCMAudio(executable="ffmpeg", source=f"sounds/{interaction.custom_id}")
            interaction.message.guild.voice_client.play(audio_source, after=self.after_playing)

    async def after_playing(self, error):
        if error:
            print(f'Player error: {error}')
        else:
            await self.bot.voice_clients[0].disconnect()

def setup(bot):
    bot.add_cog(RainCog(bot))
