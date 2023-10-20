from discord import FFmpegPCMAudio, ButtonStyle
from discord.ext import commands
from discord.ui import Button, View

class RainView(View):
    def __init__(self, rain_sounds, user_id, bot):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.bot = bot
        for i, sound in enumerate(rain_sounds):
            button = Button(style=ButtonStyle.primary, label=f"Rain Sound {i+1}", custom_id=sound)
            button.callback = self.on_button_click
            self.add_item(button)

    async def on_button_click(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the user who initiated the interaction can use these buttons.", ephemeral=True)
            return
        await self.bot.get_cog("RainCog").on_button_click(interaction)

class RainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rain_sounds = ["rain00.mp3", "rain01.mp3", "fart00.mp3"]

    @commands.slash_command(name="rain", description="Play the sound of rain")
    async def _rain(self, ctx):
        await ctx.defer()

        if ctx.author.voice is None:
            await ctx.send("You need to be in a voice channel to use this command.")
            return

        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)

        view = RainView(self.rain_sounds, ctx.author.id, self.bot)
        await ctx.respond("Please select a rain sound:", view=view)


    @commands.Cog.listener()
    async def on_button_click(self, interaction):
        if interaction.custom_id in self.rain_sounds:
            if interaction.response.is_done():
                await interaction.followup.send(f"{self.bot.user.mention} started playing the sound of the rain 🌧️")
            else:
                await interaction.response.defer()

            if interaction.message.guild.voice_client is not None:
                await interaction.followup.send(f"{self.bot.user.mention} started playing the sound of the rain 🌧️")
                audio_source = FFmpegPCMAudio(executable="ffmpeg", source=f"sounds/{interaction.custom_id}")
                interaction.message.guild.voice_client.stop()
                interaction.message.guild.voice_client.play(audio_source, after=self.after_playing)
            else:
                await interaction.followup.send(f" I am not connected to a voice channel, please use a command to call me! 🌝")

    async def after_playing(self, error):
        if error:
            print(f'Player error: {error}')
        else:
            await self.bot.voice_clients[0].disconnect()

def setup(bot):
    bot.add_cog(RainCog(bot))

