async def add_reactions(message, reactions):
    for reaction in reactions:
        await message.add_reaction(reaction)

async def handle_reactions(message):
    clean_message = message.content.lower()
    if (
        "pluie" in clean_message or
        "rain" in clean_message or
        "goutte" in clean_message or
        "raindrop" in clean_message
    ):
        await add_reactions(message, ["🌧️"])
