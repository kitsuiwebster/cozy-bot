from discord import FFmpegPCMAudio, ButtonStyle
from discord.ext import commands
from discord.ui import Button, View

# SparklesView class inherits from View and represents the interactive view for sparkles sound selection.
class SparklesView(View):
    def __init__(self, sparkles_sounds, user_id, bot):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.bot = bot
        self.sparkles_sounds = sparkles_sounds
        self.sound_labels = bot.get_cog("SparklesCog").sound_labels

        # Create buttons for each sparkles sound.
        for i, sound in enumerate(self.sparkles_sounds):
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
            await interaction.response.send_message("Only the user who typed the command can use these buttons.😵‍💫 Use the commands instead.", ephemeral=True)
            return
        
        # Handle stop button click.
        if interaction.custom_id == "stop":
            # Retrieve the guild_id and pass it to the stop_sound method
            guild_id = interaction.guild.id
            await self.bot.get_cog("SparklesCog").stop_sound(interaction, guild_id)

        else:
            # Handle sparkles sound button click.
            await self.bot.get_cog("SparklesCog").on_button_click(interaction)


# SparklesCog class is a cog for the bot that handles sparkles sound related commands.    
class SparklesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.guild_states = {}  
        # List of sparkles sound file names and mapping to emoji labels
        self.sparkles_sounds = ["sparkles00.mp3", "sparkles01.mp3", "sparkles02.mp3", "sparkles03.mp3", "sparkles04.mp3"]
        # Mapping of sound file names to emoji labels.
        self.sound_labels = {
            "sparkles00.mp3": "✨🪄⭐",
            "sparkles01.mp3": "✨🌟💫",
            "sparkles02.mp3": "✨🪄💎",
            "sparkles03.mp3": "✨🌲🌙",
            "sparkles04.mp3": "✨🪄💫"
        }

    # Slash command to play sparkles sound.
    @commands.slash_command(name="sparkles", description="Play the sound of sparkles.✨")
    async def _sparkles(self, ctx):
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

        # Create and display the SparklesView with buttons for sparkles sound selection.
        view = SparklesView(self.sparkles_sounds, ctx.author.id, self.bot)
        await ctx.respond("Please select a sparkles sound:", view=view)

    # Callback function called after a sound finishes playing.
    def after_playing(self, error, guild_id):
        guild_state = self.get_guild_state(guild_id)
        if error:
            print(f'Player error: {error}')
            return
        if not guild_state['stopped'] and guild_state['looping'] and guild_state['current_sound']:
            voice_client = self.bot.get_guild(guild_id).voice_client
            if voice_client and voice_client.is_connected():
                audio_source = FFmpegPCMAudio(executable="ffmpeg", source=f"sounds/{guild_state['current_sound']}")
                voice_client.play(audio_source, after=lambda e: self.after_playing(e, guild_id))


    def get_guild_state(self, guild_id):
        if guild_id not in self.guild_states:
            self.guild_states[guild_id] = {'stopped': False, 'looping': True, 'current_sound': None}
        return self.guild_states[guild_id]
                 
    # Listener for button click events.
    @commands.Cog.listener()
    async def on_button_click(self, interaction):
        guild_id = interaction.guild.id
        guild_state = self.get_guild_state(guild_id)

        # Handle sparkles sound selection.
        if interaction.custom_id in self.sparkles_sounds:
            if interaction.response.is_done():
                await interaction.followup.send(f"You chose {self.sound_labels[interaction.custom_id]}")
            else:
                await interaction.response.defer()

            guild_state['current_sound'] = interaction.custom_id
            guild_state['stopped'] = False
            voice_client = interaction.guild.voice_client

            if voice_client is not None:
                voice_client.stop()
                audio_source = FFmpegPCMAudio(executable="ffmpeg", source=f"sounds/{guild_state['current_sound']}")
                voice_client.play(audio_source, after=lambda e: self.after_playing(e, guild_id))
                await interaction.followup.send(f"Playing {self.sound_labels[interaction.custom_id]}")
            else:
                await interaction.followup.send("I am not connected to a voice channel, please use a command to call me.🙃")

        # Handle stop button click.
        elif interaction.custom_id == "stop":
            await self.stop_sound(interaction, guild_id)

    # Method to stop the currently playing sound.
    async def stop_sound(self, interaction, guild_id):
        guild_state = self.get_guild_state(guild_id)
        guild_state['stopped'] = True
        voice_client = interaction.guild.voice_client
        if voice_client:
            if voice_client.is_playing():
                voice_client.stop()
            await voice_client.disconnect()
            # Ensure you are sending a follow-up response if the initial response was already sent.
            if interaction.response.is_done():
                await interaction.followup.send("Sound stopped.")
            else:
                await interaction.response.send_message("Sound stopped.")
        else:
            # Handle the case where the bot is not in a voice channel.
            message = "I am not in a voice channel, I can't be stopped."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)

# Function to add the SparklesCog to the bot.
def setup(bot):
    bot.add_cog(SparklesCog(bot))
