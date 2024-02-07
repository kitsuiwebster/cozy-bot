from discord.ext import commands

class TotalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="total", description="Find out how many are currently soaking in coziness with me!")
    async def total(self, ctx):
        total_people_with_bot = 0

        for guild in self.bot.guilds:
            voice_state = guild.voice_client
            if voice_state and voice_state.channel:
                member_count = len(voice_state.channel.members) - 1
                total_people_with_bot += member_count

        if total_people_with_bot == 1:
            message = "Right now, 1 soul is wrapped in the warmth of my cozy ambiance. 😇"
        elif total_people_with_bot > 1:
            message = f"Right now, {total_people_with_bot} souls are wrapped in the warmth of my cozy ambiances. 😇"
        else:
            message = "No one is currently with me in a voice channel... Maybe it's time for you to call me? 👀"

        await ctx.respond(message)

def setup(bot):
    bot.add_cog(TotalCog(bot))
