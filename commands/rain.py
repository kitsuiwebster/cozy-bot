from discord import FFmpegPCMAudio, ButtonStyle
from discord.ext import commands
from discord.ui import Button, View

class RainView(View):
    def __init__(self, rain_sounds, user_id, bot):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.bot = bot
        self.rain_sounds = rain_sounds
        self.sound_labels = bot.get_cog("RainCog").sound_labels
        for i, sound in enumerate(self.rain_sounds):
            button = Button(style=ButtonStyle.secondary, label=self.sound_labels[sound], custom_id=sound)
            button.callback = self.on_button_click
            self.add_item(button)

        stop_button = Button(style=ButtonStyle.danger, label="Stop",emoji="⏹", custom_id="stop")
        stop_button.callback = self.on_button_click
        self.add_item(stop_button)

    async def on_button_click(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the user who typed the command can use these buttons.😵‍💫", ephemeral=True)
            return
        
        if  interaction.custom_id == "stop":
            await self.bot.get_cog("RainCog").stop_sound(interaction)

        else: 
            await self.bot.get_cog("RainCog").on_button_click(interaction)
        
class RainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.stopped = False
        self.looping = True
        self.rain_sounds = ["rain00.mp3", "rain01.mp3", "rain02.mp3", "rain03.mp3", "rain04.mp3"]
        self.sound_labels = {
            "rain00.mp3": "🌧️💧⚡",
            "rain01.mp3": "🌧️🔥🪵",
            "rain02.mp3": "🌧️💧🍃",
            "rain03.mp3": "🌧️💧🚅",
            "rain04.mp3": "🌧️🚗⚡",
        }

    @commands.slash_command(name="rain", description="Play the sound of rain.🌧️")
    async def _rain(self, ctx):
        await ctx.defer()

        if ctx.author.voice is None:
            await ctx.respond(content="You need to be in a voice channel to use this command.😵", ephemeral=True)
            return

        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)

        view = RainView(self.rain_sounds, ctx.author.id, self.bot)
        await ctx.respond("Please select a rain sound:", view=view)

    def after_playing(self, error):
        if error:
            print(f'Player error: {error}')
        else:
            if not self.stopped:
                if self.looping:
                    audio_source = FFmpegPCMAudio(executable="ffmpeg", source=f"sounds/{self.current_sound}")
                    self.bot.voice_clients[0].play(audio_source, after=self.after_playing)
                else:
                    pass

    @commands.Cog.listener()
    async def on_button_click(self, interaction):
        if interaction.custom_id in self.rain_sounds:
            if interaction.response.is_done():
                await interaction.followup.send(f"You chose {self.sound_labels[interaction.custom_id]}")
            else:
                await interaction.response.defer()

            if interaction.message.guild.voice_client is not None:
                await interaction.followup.send(f"You chose {self.sound_labels[interaction.custom_id]}")
                self.current_sound = interaction.custom_id
                audio_source = FFmpegPCMAudio(executable="ffmpeg", source=f"sounds/{self.current_sound}")
                interaction.message.guild.voice_client.stop()
                interaction.message.guild.voice_client.play(audio_source, after=self.after_playing)
            else:
                await interaction.followup.send(f" I am not connected to a voice channel, please use a command to call me.🙃")
        elif interaction.custom_id == "stop":
            await self.stop_sound(interaction)
            await interaction.followup.send(f"You chose to stop the sound")


    async def stop_sound(self, interaction):
        if interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            self.stopped = True
            await interaction.response.send_message("Sound stopped.", ephemeral=True)

def setup(bot):
    bot.add_cog(RainCog(bot))
