async def add_reactions(message, reactions):
    for reaction in reactions:
        await message.add_reaction(reaction)

async def handle_reactions(message):
    clean_message = message.content.lower()
    
    if "aime" in clean_message or "love" in clean_message:
        await add_reactions(message, ["❤️"])
    if "tg" in clean_message:
        await add_reactions(message, ["🇹", "🇬"])
    if "yo" in clean_message:
        await add_reactions(message, ["👋"])
    if "anniversaire" in clean_message or"birthday" in clean_message:
        await add_reactions(message, ["🎉", "🎂", "🥳"])
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
    if "merci" in clean_message or "thank" in clean_message:
        await add_reactions(message, ["🙏"])
    if (
        "vois" in clean_message or
        "voir" in clean_message or
        "see" in clean_message or
        "vu" in clean_message
    ):
        await add_reactions(message, ["👀"])
    if (
        "imène" in clean_message or
        "imene" in clean_message or
        "bulle" in clean_message or
        "bubble" in clean_message or
        "bulle" in clean_message or
        "emmi" in clean_message or
        "bubulle" in clean_message
    ):
        await add_reactions(message, ["🫧"])
    if (
        "suce" in clean_message or
        "pepon" in clean_message or
        "pépon" in clean_message or
        "kékro" in clean_message or
        "suck" in clean_message
    ):
        await add_reactions(message, ["👅"])
        