from discord.ext import commands

class TotalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="total", description="Find out how many are currently soaking in coziness with me!")
    async def total(self, ctx):
        total_people_with_bot = 0
        people_names = []

        for guild in self.bot.guilds:
            voice_state = guild.voice_client
            if voice_state and voice_state.channel:
                for member in voice_state.channel.members:
                    if not member.bot:  # Excluding the bot itself from the count and list
                        people_names.append(member.display_name)
                        total_people_with_bot += 1

        target_channel = self.bot.get_channel(1209607226000547883)  # Get the specific channel by ID

        if total_people_with_bot == 1:
            message = f"Right now, 1 soul is wrapped in the warmth of my cozy ambiance."
            names_message = f"{people_names[0]}"
        elif total_people_with_bot > 1:
            names = ", ".join(people_names)  # Joining all names into a single string separated by commas
            message = f"Right now, {total_people_with_bot} souls are wrapped in the warmth of my cozy ambiance."
            names_message = f"{names}"
        else:
            message = "No one is currently with me in a voice channel... Maybe it's time for you to call me? 👀"
            names_message = ""

        await ctx.respond(message)  # Send the total count to the context channel
        if names_message:
            await target_channel.send(names_message)  # Send the names to the specified channel

def setup(bot):
    bot.add_cog(TotalCog(bot))

