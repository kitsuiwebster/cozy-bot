async def add_reactions(message, reactions):
    for reaction in reactions:
        await message.add_reaction(reaction)

async def handle_reactions(message):
    clean_message = message.content.lower()
    
    # Comprehensive multilingual rain terminology database
    rain_keywords = [
        # European language variants
        # French language terms
        "pluie", "pluvieux", "pleuvoir", "pleut", "goutte", "gouttelette", "verse", "averse", "ondée", "bruine", "crachin", "giboulée",
        # English language terms  
        "rain", "raining", "rainy", "drizzle", "shower", "downpour", "raindrop", "rainfall",
        # Spanish language terms
        "lluvia", "llover", "lloviendo", "llueve", "gota", "chubasco", "aguacero", "llovizna",
        # German language terms
        "regen", "regnen", "regnet", "regnerisch", "tropfen", "regentropfen", "niederschlag", "regenschauer",
        # Italian language terms
        "pioggia", "piovere", "piove", "goccia", "acquazzone", "pioggerella",
        # Portuguese language terms
        "chuva", "chover", "chove", "gota", "aguaceiro", "garoa",
        # Dutch
        "regen", "regenen", "regent", "druppel", "regendruppel", "bui", "neerslag",
        # Swedish
        "regn", "regna", "regnar", "droppe", "regndroppe", "skyfall", "duggregn",
        # Norwegian
        "regn", "regne", "regner", "dråpe", "regndråpe", "regnvær", "yr",
        # Danish
        "regn", "regne", "regner", "dråbe", "regndråbe", "regnvejr", "støvregn",
        # Finnish
        "sade", "sataa", "satanut", "pisara", "sateenpisara", "vesisade", "tihkusade",
        # Polish
        "deszcz", "padać", "pada", "kropla", "kropla deszczu", "ulewa", "mżawka",
        # Czech
        "déšť", "pršet", "prší", "kapka", "dešťová kapka", "liják", "mrholení",
        # Slovak
        "dážď", "pršať", "prší", "kvapka", "dažďová kvapka", "lejak", "mrholenie",
        # Hungarian
        "eső", "esik", "esett", "csepp", "esőcsepp", "zápor", "szitálás",
        # Romanian
        "ploaie", "ploua", "plouă", "picătură", "picătură de ploaie", "aversă",
        # Greek
        "βροχή", "βρέχει", "σταγόνα", "ψιχάλα",
        # Bulgarian
        "дъжд", "вали", "капка", "ръмеж", "ситен дъжд",
        # Croatian/Serbian/Bosnian
        "kiša", "padati", "pada", "kap", "kap kiše", "pljusak", "rosulja",
        # Slovenian
        "dež", "padati", "pada", "kaplja", "kaplja dežja", "naliv",
        # Lithuanian
        "lietus", "lyti", "lyja", "lašas", "lietaus lašas",
        # Latvian
        "lietus", "līt", "līst", "piliens", "lietus piliens",
        # Estonian
        "vihm", "sadama", "sajab", "tilk", "vihmatilk",
        # Irish
        "báisteach", "ag cur báistí", "braon", "ceathanna",
        # Welsh
        "glaw", "glawio", "bwrw glaw", "diferyn", "cawodydd",
        # Basque
        "euria", "euri egin", "euri egiten du", "tanta",
        # Catalan
        "pluja", "ploure", "plou", "gota", "xàfec", "plugim",
        # Galician
        "chuvia", "chover", "chove", "gota", "aguaceiro",
        
        # Slavic language family
        # Russian
        "дождь", "дождик", "идёт дождь", "капля", "ливень", "дождливый", "дождичек",
        # Ukrainian
        "дощ", "йде дощ", "крапля", "зливa", "дощовий",
        # Belarusian
        "дождж", "ідзе дождж", "кропля", "лівень",
        
        # Asian language variants
        # Chinese (Simplified)
        "雨", "下雨", "雨水", "雨滴", "降雨", "雨天", "阵雨", "暴雨", "毛毛雨",
        # Chinese (Traditional)
        "雨", "下雨", "雨水", "雨滴", "降雨", "雨天", "陣雨", "暴雨", "毛毛雨",
        # Japanese
        "雨", "あめ", "雨降り", "降雨", "雨粒", "雨天", "大雨", "小雨", "にわか雨",
        # Korean
        "비", "비오다", "빗물", "빗방울", "강우", "우천", "소나기", "장마",
        # Thai
        "ฝน", "ฝนตก", "หยดน้ำ", "ฝนหลาก",
        # Vietnamese
        "mưa", "trời mưa", "giọt mưa", "mưa to", "mưa phùn", "mưa rào",
        # Indonesian/Malay
        "hujan", "turun hujan", "tetes hujan", "hujan lebat", "gerimis",
        # Tagalog/Filipino
        "ulan", "umulan", "patak ng ulan", "malakas na ulan", "ambon",
        # Hindi
        "बारिश", "बारिश होना", "बूंद", "वर्षा", "बरसात", "मूसलाधार बारिश",
        # Bengali
        "বৃষ্টি", "বৃষ্টি হওয়া", "ফোঁটা", "বর্ষা", "ঝড়বৃষ্টি",
        # Tamil
        "மழை", "மழை பெய்ய", "துளி", "கனமழை",
        # Telugu
        "వర్షం", "వర్షం పడు", "చుక్క", "కుండపోత వర్షం",
        # Gujarati
        "વરસાદ", "વરસાદ પડવો", "ટીપું", "મુશળધાર વરસાદ",
        # Marathi
        "पाऊस", "पाऊस पडणे", "थेंब", "मुसळधार पाऊस",
        # Punjabi
        "ਮੀਂਹ", "ਮੀਂਹ ਪੈਣਾ", "ਬੂੰਦ", "ਮੁਸਲਾਧਾਰ ਮੀਂਹ",
        # Urdu
        "بارش", "بارش ہونا", "قطرہ", "تیز بارش",
        # Nepali
        "वर्षा", "वर्षा हुनु", "थोपा", "ठूलो वर्षा",
        # Sinhala
        "වර්ෂාව", "වැස්ස", "බිංදුව", "විශාල වර්ෂාව",
        # Burmese
        "မိုး", "မိုးရွာ", "မိုးတစ်စက်", "မိုးကြီး",
        # Khmer
        "ភ្លៀង", "ភ្លៀងធ្លាក់", "តំណក់ភ្លៀង",
        # Lao
        "ຝົນ", "ຝົນຕົກ", "ຢອດຝົນ",
        
        # Middle Eastern and African languages
        # Arabic
        "مطر", "أمطار", "تمطر", "قطرة", "زخات", "رذاذ",
        # Hebrew
        "גשם", "יורד גשם", "טיפה", "ממטר", "טפטוף",
        # Persian/Farsi
        "باران", "باران می‌بارد", "قطره",
        # Turkish
        "yağmur", "yağmur yağmak", "damla", "sağanak", "çisenti",
        # Kurdish
        "baran", "baran dibarîne", "qetrî",
        # Azerbaijani
        "yağış", "yağmur", "damcı", "leysan",
        # Georgian
        "წვიმა", "წვიმს", "წვეთი",
        # Armenian
        "անձրև", "անձրև է գալիս", "կաթիլ",
        # Amharic
        "ዝናብ", "ዝናብ ይዘንባል", "ጠብታ",
        # Swahili
        "mvua", "kunyesha", "tone la mvua", "mvua kubwa",
        # Yoruba
        "òjò", "òjò rọ̀", "àkun òjò",
        # Igbo
        "mmiri ozuzo", "mmiri na-ezo", "mkpụrụ mmiri",
        # Hausa
        "ruwan sama", "ana ruwan sama", "digo",
        # Zulu
        "imvula", "kuya kunetha", "ithonsi lemvula",
        # Afrikaans
        "reën", "dit reën", "reëndruppel", "stortreën",
        
        # Indigenous American languages
        # Quechua
        "para", "para tamun", "sutuy",
        # Guarani
        "ama", "oky ama", "ama'i",
        # Nahuatl
        "quiahuitl", "quiahui", "atlitetl",
        
        # Pacific Islander languages
        # Hawaiian
        "ua", "ua hele", "punawai",
        # Maori
        "ua", "he ua", "matawai",
        # Samoan
        "timu", "timu ai", "matāua",
        # Fijian
        "uca", "uca tu", "dovu ni uca",
        
        # Artificial language constructs
        # Esperanto
        "pluvo", "pluvas", "pluvo guto", "pluvego",
        
        # Unicode symbols and emoji representations
        "☔", "🌧️", "💧"
    ]
    
    # Scan message content for rain-related terminology
    if any(keyword in clean_message for keyword in rain_keywords):
        await add_reactions(message, ["🌧️", "💧", "☔"])
