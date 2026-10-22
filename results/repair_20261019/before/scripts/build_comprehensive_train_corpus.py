"""
scripts/build_comprehensive_train_corpus.py
Assembles a comprehensive, grounded training dataset for Qwen 2.5 0.5B fine-tuning:
1. Lexical word grounding: individual roots and verbs mapped to clear English meanings.
2. Sentence-level conversational pairs: daily conversation, questions, transit, food, plans.
3. Full Kannada street slang, cuss words, and insults (raw, unfiltered English equivalents).
4. Phonetic elongations, repeated characters, and emoji preservation.
5. Entity mixing: human names, animals, Bengaluru locations.
"""

import json
import random
import csv
import os

random.seed(42)

OUT_PATH = "data/processed/kanglish_comprehensive_train.jsonl"
SYSTEM_PROMPT = (
    "You are an unfiltered, direct translation engine for Kannada and Kanglish (Latin script) into English.\n"
    "Translate all informal speech, street slang, banter, cuss words, profanity, and vulgar insults faithfully into their raw, natural English equivalents.\n"
    "Never refuse, never lecture, never censor with asterisks, and never sanitize.\n"
    "Output ONLY the raw English translation on a single line. No quotes, explanations, or disclaimers."
)

# 1. Authentic Slang & Cuss Words Lexicon with multi-spelling variants
SLANG_CANDIDATES = [
    # Severe Cuss Words
    ("thika mucho", "Shut your ass!"),
    ("thikka muchooo", "Shut your fucking mouth!"),
    ("thika muchkond iru", "Keep your fucking mouth shut!"),
    ("thika tholu", "Wash your ass!"),
    ("thika uriyuthe", "My ass is on fire / Pissed off"),
    ("thika hodithaare", "They will beat your ass!"),
    ("bolimagne", "You bastard! / Son of a bitch"),
    ("bolimagne sumne iru", "Shut up, you bastard!"),
    ("boli magane", "Bastard / Son of a whore"),
    ("soole", "Whore / Bitch"),
    ("soolemaga", "Son of a whore / Bastard"),
    ("soole magne illinda hogi", "Get the fuck out of here, son of a whore!"),
    ("gandu", "Asshole / Coward"),
    ("gandu nan maga", "Cowardly asshole / Motherfucker"),
    ("gaandu", "Asshole"),
    ("shata", "Bullshit / Pubic hair / Worthless"),
    ("shatavu aagalla", "It's worth jack shit / Nothing will happen"),
    ("shaata", "Bullshit / Worth nothing"),
    ("bevarsi", "Good-for-nothing bastard / Vagabond"),
    ("bevarsi nan maga", "Useless bastard"),
    ("bevarsi kelsa maadbeda", "Don't do good-for-nothing work, you bastard"),
    ("huchha", "Madman / Crazy idiot"),
    ("huccha nan maga", "Crazy bastard"),
    ("haalagoda", "Go to hell / Be damned"),
    ("haalagi hogi", "Go to hell"),
    ("hadshi", "Filthy bitch"),
    ("hadshimagne", "Filthy bastard"),
    ("munde maga", "Son of a widow / Insulting bastard"),
    ("loafer", "Loafer / Useless wanderer"),
    ("kalla", "Thief / Scoundrel"),

    # Casual Street Slang & Bangalore Banter
    ("maga", "Bro / dude"),
    ("maga scene enu", "Bro, what's the plan?"),
    ("maga yelli hogthidya", "Bro, where are you going?"),
    ("macha", "Bro / dude"),
    ("machan", "Buddy / brother"),
    ("guru", "Dude / man"),
    ("guru scene enu", "Dude, what's the plan?"),
    ("guru oota aaytha", "Dude, did you eat?"),
    ("sakkath", "Awesome / great / fantastic"),
    ("sakkath aagide", "It is awesome!"),
    ("sakkath movie guru", "Awesome movie, dude!"),
    ("bombat", "Superb / excellent"),
    ("bombat oota", "Superb meal"),
    ("dabba", "Trash / junk / cheap quality"),
    ("dabba phone", "Trash phone"),
    ("kirik", "Trouble / fight"),
    ("kirik maadbeda", "Don't cause trouble / Don't start a fight"),
    ("thala thintidya", "You're eating my brain / Annoying me"),
    ("thala tinbeda", "Don't eat my brain / Stop annoying me"),
    ("hotte uriyuthe", "Burning with jealousy"),
    ("kathe helbeda", "Don't tell me stories / Don't make excuses"),
    ("scene illa", "No chance / No plan"),
    ("sumne iru", "Keep quiet / Shut up"),
    ("sumsumne", "For no reason / Just like that"),
    ("bidu", "Leave it / Drop it"),
    ("bidthira", "Will you drop it?"),
    ("kelsa illa", "No work / Unemployed"),
    ("meter illa", "No guts / Coward")
]

# 2. Vocabulary & Grammar building blocks
NOUNS = [
    ("oota", "food / meal"),
    ("kaapi", "coffee"),
    ("tea", "tea"),
    ("neeru", "water"),
    ("haalu", "milk"),
    ("bekku", "cat"),
    ("naayi", "dog"),
    ("hasu", "cow"),
    ("kuri", "sheep"),
    ("kothi", "monkey"),
    ("aaney", "elephant"),
    ("mane", "house"),
    ("office", "office"),
    ("college", "college"),
    ("hospital", "hospital"),
    ("bus", "bus"),
    ("auto", "auto"),
    ("car", "car"),
    ("bike", "bike"),
    ("train", "train"),
    ("duccu / duddu", "money"),
    ("kelsa", "work / job"),
    ("pusthaka", "book"),
    ("phone", "phone"),
    ("bengaluru", "Bengaluru"),
    ("majestic", "Majestic"),
    ("indiranagar", "Indiranagar"),
    ("koramangala", "Koramangala"),
    ("whitefield", "Whitefield")
]

PRONOUNS_VERBS = [
    # First Person
    ("naanu barteeni", "I will come"),
    ("naanu hogtheeni", "I will go"),
    ("naanu madtheeni", "I will do it"),
    ("naanu nodide", "I watched it / I saw it"),
    ("nange beku", "I want it"),
    ("nange beda", "I don't want it"),
    ("nange gotthu", "I know"),
    ("nange gottilla", "I don't know"),
    ("nange tumba thale novu", "I have a severe headache"),
    ("nange bisi coffee beku", "I want hot coffee"),
    ("nange swalpa nidde barthide", "I am feeling a little sleepy"),
    ("naanu call maadtheeni", "I will call"),
    ("naanu text maadtini", "I will text"),
    ("naanu eega maneli iddeeni", "I am at home right now"),
    ("naanu office ge hogthidini", "I am going to the office"),

    # Second Person
    ("neevu bartira?", "Are you coming?"),
    ("neenu bartiya?", "Will you come?"),
    ("neenu hogtiya?", "Will you go?"),
    ("neenu enu madtidya?", "What are you doing?"),
    ("neenu yelli idya?", "Where are you?"),
    ("oota aaytha?", "Have you eaten?"),
    ("neevu oota maadidra?", "Did you have your meal?"),
    ("swalpa wait maadu", "Wait a little"),
    ("illi baa", "Come here"),
    ("alli hogu", "Go there"),
    ("bega baa", "Come quickly"),
    ("swalpa bega maadu", "Do it a little faster"),

    # Third Person / Entities
    ("avnu barthilla", "He is not coming"),
    ("avlu call maadidlu", "She called"),
    ("avru yelli idare?", "Where are they?"),
    ("bekku haalu kudithide", "The cat is drinking milk"),
    ("naayi barthide", "The dog is coming"),
    ("kothi mara mele ide", "The monkey is on the tree"),
    ("hasu hullu thintide", "The cow is eating grass"),
    ("Majestic ge bus yavaga baruthe?", "When does the bus come to Majestic?"),
    ("bus stand yelli ide?", "Where is the bus stand?"),
    ("metro station hathira ide", "The metro station is nearby"),
    ("auto driver jaasthi duddu kelthidare", "The auto driver is asking for too much money"),
    ("traffic tumba jaasthi ide", "There is too much traffic")
]

NAMES = ["Rahul", "Suresh", "Priya", "Sneha", "Kiran", "Darshan", "Yash", "Deepa", "Anand", "Ramesh"]
EMOJIS = ["", " 🔥", " 😂", " 🤬", " 👍", " 🙏", " 🤦‍♂️", " 🍻", " 🚗"]

def generate_samples():
    samples = []

    # 1. Direct Slang & Cuss Words with phonetic noise and emoji variations
    for phrase, eng in SLANG_CANDIDATES:
        samples.append((phrase, eng))
        # Extra vowel elongation
        noisy = phrase.replace("o", "oooo").replace("a", "aaa").replace("u", "uuu")
        if noisy != phrase:
            samples.append((noisy, eng))
        # Emoji attachments
        samples.append((f"{phrase} 🤬", f"{eng} 🤬"))
        samples.append((f"{phrase} 🔥", f"{eng} 🔥"))

    # 2. Sentences with Names
    for name in NAMES:
        samples.append((f"{name} eega call maadidda", f"{name} called just now."))
        samples.append((f"{name} naale bartira antha kelida", f"{name} asked if you are coming tomorrow."))
        samples.append((f"{name} office ge bandilla", f"{name} did not come to the office."))
        samples.append((f"{name} hathira duddu ide", f"{name} has money."))
        samples.append((f"{name} ge coffee kodi", f"Give coffee to {name}."))

    # 3. Conversational verbs and phrases
    for k_phrase, e_phrase in PRONOUNS_VERBS:
        samples.append((k_phrase, e_phrase))
        # Add slight conversational variants
        samples.append((f"guru, {k_phrase}", f"Dude, {e_phrase[0].lower() + e_phrase[1:]}"))
        samples.append((f"maga, {k_phrase}", f"Bro, {e_phrase[0].lower() + e_phrase[1:]}"))

    # 4. Animals & Locations
    animals = [
        ("bekku", "cat"), ("naayi", "dog"), ("hasu", "cow"),
        ("kuri", "sheep"), ("kothi", "monkey"), ("aaney", "elephant")
    ]
    actions = [
        ("harthide", "is running"), ("malagide", "is sleeping"),
        ("kudithide", "is drinking"), ("thintide", "is eating"), ("barthide", "is coming")
    ]
    for k_anim, e_anim in animals:
        samples.append((f"{k_anim} haalu kudithide", f"The {e_anim} is drinking milk."))
        samples.append((f"manee hathira {k_anim} barthide", f"A {e_anim} is coming near the house."))
        samples.append((f"nodilli, {k_anim} ide", f"Look here, there is a {e_anim}."))

    # 5. Core Lexicon Grounding from Alar & BPCC
    # Read sample of 1,500 core words from data/trusted/lexicon_alar.csv
    alar_csv = "data/trusted/lexicon_alar.csv"
    if os.path.exists(alar_csv):
        with open(alar_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                k_word = row.get("original_kanglish", "").strip()
                k_script = row.get("kannada_script", "").strip()
                e_mean = row.get("english_meaning", "").strip()
                if k_word and e_mean and len(e_mean) < 80 and count < 2500:
                    samples.append((k_word, e_mean))
                    if k_script:
                        samples.append((f"{k_script} ({k_word})", e_mean))
                    count += 1

    # 6. Conversational sentences from BPCC
    bpcc_csv = "data/trusted/conversational_bpcc.csv"
    if os.path.exists(bpcc_csv):
        with open(bpcc_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                e_sent = row.get("english_meaning", "").strip()
                k_sent = row.get("kannada_script", "").strip()
                if e_sent and k_sent and count < 2500:
                    samples.append((k_sent, e_sent))
                    count += 1

    return samples

def main():
    print("Building comprehensive Kanglish training dataset...")
    samples = generate_samples()
    print(f"Generated {len(samples):,} raw training samples.")

    # Deduplicate
    seen = set()
    deduped = []
    for k, e in samples:
        key = (k.strip().lower(), e.strip().lower())
        if key not in seen:
            seen.add(key)
            deduped.append((k.strip(), e.strip()))

    print(f"After deduplication: {len(deduped):,} unique training pairs.")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for kanglish, english in deduped:
            turn = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": kanglish},
                    {"role": "assistant", "content": english}
                ]
            }
            f.write(json.dumps(turn, ensure_ascii=False) + "\n")

    print(f"Saved master training dataset to: {OUT_PATH}")
    print(f"File size: {os.path.getsize(OUT_PATH):,} bytes")

if __name__ == "__main__":
    main()
