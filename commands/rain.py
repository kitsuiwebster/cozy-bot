from discord import FFmpegPCMAudio, ButtonStyle
from discord.ext import commands
from discord.ui import Button, View

# RainView class inherits from View and represents the interactive view for rain sound selection.
class RainView(View):
    def __init__(self, rain_sounds, user_id, bot):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.bot = bot
        self.rain_sounds = rain_sounds
        self.sound_labels = bot.get_cog("RainCog").sound_labels

        # Create buttons for each rain sound.
        for i, sound in enumerate(self.rain_sounds):
            button = Button(style=ButtonStyle.secondary, label=self.sound_labels[sound], custom_id=sound)
            button.callback = self.on_button_click
            self.add_item(button)

        # Create a stop button.
        stop_button = Button(style=ButtonStyle.danger, label="Stop",emoji="⏹", custom_id="stop")
        stop_button.callback = self.on_button_click
        self.add_item(stop_button)

    # Callback for button clicks.
    async def on_button_click(self, interaction):
        # Check if the user who clicked is the same as the one who initiated the command.
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the user who typed the command can use these buttons.😵‍💫", ephemeral=True)
            return
        
        # Handle stop button click.
        if  interaction.custom_id == "stop":
            await self.bot.get_cog("RainCog").stop_sound(interaction)

        else: 
            # Handle rain sound button click.
            await self.bot.get_cog("RainCog").on_button_click(interaction)


# RainCog class is a cog for the bot that handles rain sound related commands.
class RainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.stopped = False
        self.looping = True
        # List of rain sound file names.
        self.rain_sounds = ["rain00.mp3", "rain01.mp3", "rain02.mp3", "rain03.mp3", "rain04.mp3"]
        # Mapping of sound file names to emoji labels.
        self.sound_labels = {
            "rain00.mp3": "🌧️💧⚡",
            "rain01.mp3": "🌧️🔥🪵",
            "rain02.mp3": "🌧️💧🍃",
            "rain03.mp3": "🌧️💧🚅",
            "rain04.mp3": "🌧️🚗⚡",
        }

    # Slash command to play rain sound.
    @commands.slash_command(name="rain", description="Play the sound of rain.🌧️")
    async def _rain(self, ctx):
        await ctx.defer()

        # Check if the user is in a voice channel.
        if ctx.author.voice is None:
            await ctx.respond(content="You need to be in a voice channel to use this command.😵", ephemeral=True)
            return

        channel = ctx.author.voice.channel
        # Connect to the voice channel or move to it if already connected.
        if ctx.voice_client is None:
            await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)

        # Create and display the RainView with buttons for rain sound selection.
        view = RainView(self.rain_sounds, ctx.author.id, self.bot)
        await ctx.respond("Please select a rain sound:", view=view)

    # Callback function called after a sound finishes playing.
    def after_playing(self, error):
        if error:
            print(f'Player error: {error}')
        else:
            # If not stopped and looping is enabled, replay the current sound.
            if not self.stopped:
                if self.looping:
                    audio_source = FFmpegPCMAudio(executable="ffmpeg", source=f"sounds/{self.current_sound}")
                    self.bot.voice_clients[0].play(audio_source, after=self.after_playing)
                else:
                    pass

    # Listener for button click events.
    @commands.Cog.listener()
    async def on_button_click(self, interaction):
        # Handle rain sound selection.
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

        # Handle stop button click.
        elif interaction.custom_id == "stop":
            await self.stop_sound(interaction)
            await interaction.followup.send(f"You chose to stop the sound")

    # Method to stop the currently playing sound.
    async def stop_sound(self, interaction):
        voice_client = interaction.guild.voice_client
        if voice_client:
            # If a sound is playing, stop it and disconnect the voice client.
            if voice_client.is_playing():
                voice_client.stop()
                self.stopped = True
            await voice_client.disconnect()
            await interaction.response.send_message("Sound stopped.")
        else:
            # Send a message if the bot is not in a voice channel.
            await interaction.response.send_message("I am not in a voice channel, I can't be stopped.", ephemeral=True)


# Function to add the RainCog to the bot.
def setup(bot):
    bot.add_cog(RainCog(bot))
