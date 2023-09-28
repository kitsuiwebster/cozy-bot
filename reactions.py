async def add_reactions(message, reactions):
    for reaction in reactions:
        await message.add_reaction(reaction)

async def handle_reactions(message):
    clean_message = message.content.lower()
    if (
        "!story" in clean_message or
        "!softstory" in clean_message or
        "!dialogue" in clean_message or
        "!dilemma" in clean_message or
        "!situation" in clean_message or
        "!encode" in clean_message or
        "!dihia" in clean_message or
        "!cmd" in clean_message or
        "!poof" in clean_message or
        "!ask" in clean_message or
        "!join" in clean_message or
        "!leave" in clean_message or
        "!rain" in clean_message
    ):
        await add_reactions(message, ["✅"])
