import asyncio
from discord.ext import commands
import os
import random
from pydub import AudioSegment
from discord import FFmpegPCMAudio, ButtonStyle
from interactions import *
import uuid
from discord.ui import Button, View







class AmbientView(View):
    def __init__(self, user_id, bot):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.bot = bot

        # Button for pausing the sound
        pause_button = Button(style=ButtonStyle.danger, label="Pause",emoji="⏸", custom_id="pause")
        pause_button.callback = self.on_button_click
        self.add_item(pause_button)

        # Button for resuming the sound
        resume_button = Button(style=ButtonStyle.success, label="Resume",emoji="▶", custom_id="resume")
        resume_button.callback = self.on_button_click
        self.add_item(resume_button)

        # Button for looping the sound
        loop_button = Button(style=ButtonStyle.primary, label="Loop", emoji="🔁", custom_id="loop")
        loop_button.callback = self.on_button_click
        self.add_item(loop_button)

        # Button for playing a new sound
        play_new_button = Button(style=ButtonStyle.secondary, label="Play New Sound",emoji="⏭", custom_id="play_new")
        play_new_button.callback = self.on_button_click
        self.add_item(play_new_button)


    async def on_button_click(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the user who initiated the interaction can use these buttons.", ephemeral=True)
            return

        custom_id = interaction.data['custom_id']

        if custom_id == "pause":
            # Handle pause action
            # Pause the currently playing sound
            await self.bot.get_cog("AmbientCog").pause_sound(interaction)

        elif custom_id == "resume":
            # Handle resume action
            # Resume the paused sound
            await self.bot.get_cog("AmbientCog").resume_sound(interaction)
        
        elif custom_id == "loop":
            # Handle loop action
            # Loop the current sound
            await self.bot.get_cog("AmbientCog").loop_sound(interaction)
        elif custom_id == "play_new":
            # Handle play new sound action
            # Play a new sound
            await self.bot.get_cog("AmbientCog").play_new_sound(interaction)

        else:
            # Handle individual sound button action
            await self.bot.get_cog("AmbientCog").on_button_click(interaction)







# Générer un nom de fichier aléatoire avec uuid
file_name = str(uuid.uuid4()) + '.mp3'
file_path = os.path.join('samples', file_name)
ambient_folder = 'ambient'
audio_files = os.listdir(ambient_folder)
selected_files = random.sample(audio_files, 3)







class AmbientCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.paused = False


        
        # Chargez les fichiers audio sélectionnés
        selected_sounds = [AudioSegment.from_file(os.path.join(ambient_folder, file)) for file in selected_files]

        # Trouvez la durée minimale parmi les sons sélectionnés
        min_duration = min(sound.duration_seconds for sound in selected_sounds)

        # Ajustez la longueur de chaque son sélectionné à la durée minimale
        selected_sounds = [sound[:min_duration * 1000] for sound in selected_sounds]

        # Superposez les trois sons
        combined_sound = selected_sounds[0].overlay(selected_sounds[1]).overlay(selected_sounds[2])

        # Exportez le son superposé dans un fichier temporaire
        #combined_sound.export('combined_sound.mp3', format='mp3')
        combined_sound.export(file_path, format='mp3')







    @commands.slash_command(description="Customize ambient sounds to chill")
    async def ambient(self, ctx):
        await ctx.defer()

        if ctx.author.voice is None:
            await ctx.send("You need to be in a voice channel to use this command.")
            return
    
        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)
        # Send a message in the text channel where the command was invoked
        view = AmbientView(ctx.author.id, self.bot)
        await ctx.respond(f"{ctx.author.mention} has called {self.bot.user.mention} to listen to ambient sounds 🎍.", view=view)

        #while True:
        # Jouez le fichier temporaire
        ctx.voice_client.play(FFmpegPCMAudio(file_path))

        while ctx.voice_client.is_playing():
            await asyncio.sleep(1)

        #await ctx.voice_client.disconnect()



    @commands.Cog.listener()
    async def on_button_click(self, interaction):
        custom_id = interaction.component['custom_id']
        if custom_id == "pause":
            await self.pause_sound(interaction)
        elif custom_id == "resume":
            await self.resume_sound(interaction)
        elif custom_id == "loop":
            await self.loop_sound(interaction)
        elif custom_id == "play_new":
            await self.play_new_sound(interaction)
        else:
            # Handle individual sound button click
            # You can implement this based on your requirements
            pass

    async def pause_sound(self, interaction):
        if interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            self.paused = True
            await interaction.response.send_message("Sound paused.", ephemeral=True)

    async def resume_sound(self, interaction):
        if not interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.resume()
            self.paused = False
            await interaction.response.send_message("Sound resumed.", ephemeral=True)

    async def loop_sound(self, interaction):
        if interaction.guild.voice_client.is_playing():
            # Set a flag to indicate looping
            self.looping = True
            await interaction.response.send_message("Sound will now loop.", ephemeral=True)


    def on_audio_finished(self, interaction, error):
        if not self.paused:
            # Play the next sound if not paused
            # You can implement this based on your requirements
            pass





def setup(bot):
    bot.add_cog(AmbientCog(bot))
