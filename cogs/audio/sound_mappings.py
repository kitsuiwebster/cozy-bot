# Central mapping of sound filenames to emoji display names

SOUND_LABELS = {
    # Rain sounds
    "rain00.mp3": "🌧️💧⚡",
    "rain01.mp3": "🌧️🌿🌙",
    "rain02.mp3": "🌧️⛈️💨",
    "rain03.mp3": "🌧️🏠🔥",
    "rain04.mp3": "🌧️🚗⚡",
    "rain05.mp3": "🌧️⚡🐦",
    "rain06.mp3": "🌧️🐦🌿",
    "rain07.mp3": "🌧️⚡💦",
    "rain08.mp3": "🌧️🔥⛺",
    "rain09.mp3": "🌧️🧚🏻‍♀🌲",

    # Sea sounds
    "sea00.mp3": "🌊💧💦",
    "sea01.mp3": "🌊🕊️⛱️",
    "sea02.mp3": "🌊🏝️🌙",
    "sea03.mp3": "🌊⛵🕊️",
    "sea04.mp3": "🌊🤿🔱",

    # Sparkles sounds
    "sparkles00.mp3": "✨🪄⭐",
    "sparkles01.mp3": "✨🌟💫",
    "sparkles02.mp3": "✨🪄💎",
    "sparkles03.mp3": "✨🌲🌙",
    "sparkles04.mp3": "✨🪄💫",

    # Background music
    "background-music00.mp3": "🎶🏛️🌙",
    "background-music01.mp3": "🎶🍃🌩️",
    "background-music02.mp3": "🎶🏺💦",
    "background-music03.mp3": "🎶🌸💦",
    "background-music04.mp3": "🎶🌿💦",

    # Noise sounds
    "noise00.mp3": "📡⏳🔜",
    "noise01.mp3": "📡🤍🌌",
    "noise02.mp3": "📡⏳🔜",
    "noise03.mp3": "📡⏳🔜",
    "noise04.mp3": "📡⏳🔜",
}

def get_sound_display_name(sound_filename: str) -> str:
    """Get emoji display name for a sound filename"""
    return SOUND_LABELS.get(sound_filename, sound_filename)

