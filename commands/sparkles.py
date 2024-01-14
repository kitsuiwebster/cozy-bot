from discord import FFmpegPCMAudio, ButtonStyle
from discord.ext import commands
from discord.ui import Button, View

class SparklesView(View):
    def __init__(self, sparkles_sounds, user_id, bot):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.bot = bot
        self.sparkles_sounds = sparkles_sounds
        self.sound_labels = bot.get_cog("SparklesCog").sound_labels
        for i, sound in enumerate(self.sparkles_sounds):
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
            await self.bot.get_cog("SparklesCog").stop_sound(interaction)

        else: 
            await self.bot.get_cog("SparklesCog").on_button_click(interaction)
        
class SparklesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.stopped = False
        self.looping = True
        self.sparkles_sounds = ["sparkles00.mp3", "sparkles01.mp3", "sparkles02.mp3", "sparkles03.mp3"]
        self.sound_labels = {
            "sparkles00.mp3": "✨🪄⭐",
            "sparkles01.mp3": "✨🌟💫",
            "sparkles02.mp3": "✨🪄💎",
            "sparkles03.mp3": "✨🌲🌙",
        }

    @commands.slash_command(name="sparkles", description="Play the sound of sparkles.✨")
    async def _sparkles(self, ctx):
        await ctx.defer()

        if ctx.author.voice is None:
            await ctx.respond(content="You need to be in a voice channel to use this command.😵", ephemeral=True)
            return

        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)

        view = SparklesView(self.sparkles_sounds, ctx.author.id, self.bot)
        await ctx.respond("Please select a sparkles sound:", view=view)

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
        if interaction.custom_id in self.sparkles_sounds:
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
    bot.add_cog(SparklesCog(bot))
