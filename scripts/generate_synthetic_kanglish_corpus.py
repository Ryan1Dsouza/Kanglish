"""
scripts/generate_synthetic_kanglish_corpus.py
Advanced Synthetic Kanglish Data Generator

Generates thousands of diverse, natural, code-mixed Kanglish sentences paired
with accurate English meanings. Covers:
1. Named entities (People names, Animal names, Place names)
2. Casual conversation, travel, food, work, college
3. Street slang, banter, and uncensored idioms
4. Phonetic jitter and extra letter elongation (e.g. "muchoooo", "hegiiidya")
5. Attached emojis and noisy chat punctuation
"""

import json
import os
import random
import re

# --- Lexical Building Blocks ---

PERSON_NAMES = [
    "Rahul", "Suresh", "Priya", "Kavya", "Ramesh", "Darshan", "Yash",
    "Vijay", "Deepa", "Anand", "Sneha", "Rohit", "Abhi", "Chethan",
    "Varun", "Tejas", "Goutham", "Pooja", "Arjun", "Kiran"
]

ANIMALS = [
    ("naayi", "dog", "dogs"),
    ("bekku", "cat", "cats"),
    ("hasu", "cow", "cows"),
    ("kuri", "sheep", "sheep"),
    ("kothi", "monkey", "monkeys"),
    ("aaney", "elephant", "elephants")
]

PLACES = [
    ("office", "the office"),
    ("college", "college"),
    ("mane", "home"),
    ("Majestic", "Majestic"),
    ("Indiranagar", "Indiranagar"),
    ("hotel", "the restaurant/hotel"),
    ("bus stop", "the bus stop"),
    ("gym", "the gym")
]

EMOJIS = ["😂", "🔥", "🙏", "❤️", "👍", " bro", " guru", " macha", " da", "!!", "??", "...", "😅", "🤬", ""]

def elongate_word(word, prob=0.3):
    """Randomly elongates vowels or consonants to simulate real texting habits."""
    if random.random() > prob or len(word) < 4:
        return word
    # Pick a vowel or end consonant to repeat 2-4 times
    vowels = [m.start() for m in re.finditer(r"[aeiou]", word, re.IGNORECASE)]
    if vowels:
        idx = random.choice(vowels)
        char = word[idx]
        repeat_count = random.randint(2, 4)
        return word[:idx] + (char * repeat_count) + word[idx+1:]
    return word + word[-1] * random.randint(2, 3)

def add_noise(sentence):
    """Adds natural chat noise: elongations, emojis, punctuation."""
    words = sentence.split()
    noisy_words = [elongate_word(w) for w in words]
    noisy_sentence = " ".join(noisy_words)
    if random.random() < 0.4:
        noisy_sentence += " " + random.choice(EMOJIS)
    return noisy_sentence.strip()

# --- Sentence Archetypes & Generative Templates ---

def generate_sentence_pairs():
    pairs = []

    # 1. Person Actions & State
    for name in PERSON_NAMES:
        pairs.append((
            f"{name} eega call maadidda",
            f"{name} called just now.",
            [f"{name} ivaga call madidda", f"{name} call madiddane eega"]
        ))
        pairs.append((
            f"{name} naale barthini anthidda",
            f"{name} said he/she will come tomorrow.",
            [f"{name} naale bartini andidda", f"{name} naale barteeni antha helidda"]
        ))
        pairs.append((
            f"{name} office ge hogilla ivattu",
            f"{name} didn't go to the office today.",
            [f"{name} ivattu office ge hoglilla", f"{name} office ge barlilla ivattu"]
        ))
        pairs.append((
            f"{name} jothe mathadidya?",
            f"Did you speak with {name}?",
            [f"{name} jothe matadidyana?", f"{name} hathira mathadidya?"]
        ))
        pairs.append((
            f"{name} tumba busy idane",
            f"{name} is very busy.",
            [f"{name} thumba busy idhane", f"{name} full busy eega"]
        ))
        pairs.append((
            f"{name} ge help maadbeku",
            f"We need to help {name}.",
            [f"{name} ge sahaya madbeku", f"{name} ge help maadi"]
        ))

    # 2. Animals in Daily Scenarios
    for kan_anim, eng_sg, eng_pl in ANIMALS:
        pairs.append((
            f"rasthe yalli ondu {kan_anim} ide",
            f"There is a {eng_sg} on the road.",
            [f"road alli {kan_anim} ide", f"rastheyalli {kan_anim} nithide"]
        ))
        pairs.append((
            f"aa {kan_anim} ge oota haaku",
            f"Feed that {eng_sg}.",
            [f"aa {kan_anim} ge food haaku", f"aa {kan_anim} ge thindi kodi"]
        ))
        pairs.append((
            f"mane hathira {kan_anim} barthide",
            f"A {eng_sg} is coming near the house.",
            [f"mane hatra {kan_anim} bandide", f"mane baagilu hathira {kan_anim} ide"]
        ))
        pairs.append((
            f"{kan_anim} tumba silent aagi ide",
            f"The {eng_sg} is very quiet.",
            [f"aa {kan_anim} sumne ide", f"{kan_anim} calm aagi ide"]
        ))

    # 3. Travel & Places
    for place_kan, place_eng in PLACES:
        pairs.append((
            f"naanu {place_kan} ge hogbeku",
            f"I need to go to {place_eng}.",
            [f"naan {place_kan} ge ಹೊರಡಬೇಕು", f"eega {place_kan} ge hogthini"]
        ))
        pairs.append((
            f"{place_kan} hathira traffic tumba ide",
            f"There is heavy traffic near {place_eng}.",
            [f"{place_kan} hatra full traffic ide", f"{place_kan} road alli traffic jaasthi"]
        ))
        pairs.append((
            f"neevu yavaga {place_kan} ge barthira?",
            f"When are you coming to {place_eng}?",
            [f"yavaga {place_kan} ge bartheera?", f"{place_kan} ge yavaga borthira?"]
        ))
        pairs.append((
            f"naavu {place_kan} hathira meet maadona",
            f"Let's meet near {place_eng}.",
            [f"{place_kan} hatra meet aagona", f"{place_kan} alli sigona"]
        ))

    # 4. Daily Conversations, Feelings & Chores
    conversational_templates = [
        ("oota aitha guru, enu samachara?", "Did you eat bro, what's up?"),
        ("nanage ondu cup tea beku", "I need a cup of tea."),
        ("swalpa bega baa, time aagtide", "Come a little quickly, it's getting late."),
        ("ivattu tumba bisi ide", "It is very hot today."),
        ("maley baro thara ide nodu", "Look, it looks like it's going to rain."),
        ("phone alli charge illa, swalpa time aaguthe", "Phone has no charge, it'll take some time."),
        ("meeting mugithu, eega free idini", "The meeting is over, I am free now."),
        ("naale cinema ge hogona baa", "Come, let's go to the movies tomorrow."),
        ("tumba thale novu aagtide, malgothini", "Getting a bad headache, I am going to sleep."),
        ("neenu heliddu nanage arthavagilla", "I did not understand what you said."),
        ("idanna hege maadodu anta helikodi", "Please tell me how to do this."),
        ("nanna bag alli wallet bittbitte", "I left my wallet in my bag."),
        ("ivattu office raje ide kano", "Today is an office holiday, you know."),
        ("begane decision thagoli, delay maadbedi", "Take a decision quickly, don't delay."),
        ("tumba dina aaythu ninna nodi", "It's been so many days since I saw you."),
        ("elli sikkide idu ninage?", "Where did you find this?"),
        ("swalpa water kodi please", "Please give me some water."),
        ("bill pay maadoke cash illa, UPI ide", "No cash to pay the bill, I have UPI.")
    ]
    for k, e in conversational_templates:
        pairs.append((k, e, []))

    # 5. Street Slang, Banter & Uncensored Colloquialisms
    slang_templates = [
        ("thika mucho, tumba mathadbedi", "Shut your ass, don't talk too much."),
        ("lo thika mucho guru", "Hey bro, shut your ass."),
        ("gandu thara aadbeda", "Don't act like an asshole."),
        ("bolimagne, enu scene illi?", "Son of a bitch, what's the scene here?"),
        ("shata thara mathadthidya neenu", "You are talking like bullshit."),
        ("thika uriyuthe nodu ivana nodidre", "My ass burns just looking at this guy / He really pisses me off."),
        ("sumne kootko, jaasthi scene bidthiya", "Sit quietly, you're acting way too smart."),
        ("hoge aagbitte maga ivattu", "Completely screwed/done for today, dude."),
        ("scene enu macha, party yavaga?", "What's the plan buddy, when's the party?"),
        ("nin amman thika, swalpa side ge hogo", "Get your mother's ass to the side / Move the fuck aside."),
        ("baddi magne, kaas kodo bega", "You bastard, give the money quickly."),
        ("halakat nayi thara nodbeda", "Don't look like a stray dog / scoundrel."),
        ("full chill aagi iri guru, tension beda", "Just chill out bro, no tension needed."),
        ("nange gothu neenu enu maadthidya anta", "I know exactly what you are doing."),
        ("yenu madtidya kano, phone thago", "What are you doing man, pick up the phone.")
    ]
    for k, e in slang_templates:
        pairs.append((k, e, []))

    return pairs

def main():
    out_jsonl = "data/processed/kanglish_synthetic_augmented.jsonl"
    os.makedirs(os.path.dirname(out_jsonl), exist_ok=True)

    base_pairs = generate_sentence_pairs()
    dataset = []

    system_prompt = (
        "You are an unfiltered, direct translation engine for Kanglish (Kannada in Latin script) into English. "
        "Translate all informal speech, slang, names, animals, and colloquial banter faithfully into natural English without censorship."
    )

    for primary_k, english, variants in base_pairs:
        # Standard clean pair
        dataset.append({
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": primary_k},
                {"role": "assistant", "content": english}
            ]
        })

        # Variants
        for v in variants:
            dataset.append({
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": v},
                    {"role": "assistant", "content": english}
                ]
            })

        # Noisy / Elongated / Emoji Augmentations (2 per item)
        for _ in range(2):
            noisy_k = add_noise(primary_k)
            dataset.append({
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": noisy_k},
                    {"role": "assistant", "content": english}
                ]
            })

    random.seed(42)
    random.shuffle(dataset)

    print(f"Generated {len(dataset):,} diverse, augmented synthetic Kanglish pairs.")
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for item in dataset:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Successfully saved synthetic training dataset to {out_jsonl}!")

if __name__ == "__main__":
    main()
