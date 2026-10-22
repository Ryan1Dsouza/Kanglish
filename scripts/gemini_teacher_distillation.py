"""
scripts/gemini_teacher_distillation.py
Teacher-Student Knowledge Distillation using Gemini 2.5 Flash.

Uses Gemini as the "Teacher" to generate pristine, authentic Kanglish, Tulu,
and Konkani-to-English conversational pairs across real Karnataka slang,
WhatsApp chats, and daily usage.
"""
import os
import json
import time
import requests

# Load GEMINI_API_KEY from .env
ENV_FILE = ".env"
API_KEY = None
if os.path.exists(ENV_FILE):
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY="):
                API_KEY = line.strip().split("=", 1)[1]
                break

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env!")

MODEL_NAME = "gemini-flash-latest"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
OUTPUT_FILE = "data/processed/gemini_teacher_dataset.jsonl"
GLOSSARY_FILE = "data/corpus/mangalore_glossary.json"
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

# Load Trilingual Glossary Context
MANGALORE_GLOSSARY_CONTEXT = ""
if os.path.exists(GLOSSARY_FILE):
    try:
        with open(GLOSSARY_FILE, "r", encoding="utf-8") as f:
            glossary_data = json.load(f)
            lines = []
            for category, items in glossary_data.items():
                cat_title = category.replace("_", " ").title()
                terms = [f"{k} = {v}" for k, v in items.items()]
                lines.append(f"[{cat_title}]: " + "; ".join(terms))
            MANGALORE_GLOSSARY_CONTEXT = "\n".join(lines)
    except Exception as e:
        print(f"Warning: Could not load glossary: {e}")

MORPHOLOGY_GUIDE = """
COASTAL KARNATAKA (TULU, KONKANI, KANGLISH) MORPHOLOGICAL GROUNDING:
1. Tulu Verb Suffixes:
   - '-ondh ulle' / '-ondundu' = present continuous (e.g. 'tuvondh ulle' = I am watching, 'avondh undu' = is happening)
   - '-odchi' / '-podchi' = negative imperative ('malpodchi' = don't do, 'panodchi' = don't say, 'bejar malpodchi' = don't feel bad)
   - '-odu' / '-podu' = obligation / necessity ('malpodu' = must do, 'paadodu' = must put/post, 'kalpod' = must study)
   - '-uji' / '-puji' = negative present/future ('barpuje' = won't come, 'kenuji' = not audible, 'deppuji' = won't remove)
   - '-naga' = temporal marker 'when' ('thikkinaga' = when found, 'ponnaga' = when going, 'lakenaga' = when waking up)
   - 'ge' = evidential marker 'apparently / it seems / they say' ('lepuver ge' = apparently they call, 'bolla ge' = it seems there's flooding)
2. Mangalorean Konkani Markers:
   - 'asa' (is/exists), 'zale' (done/happened), 'zavna' (couldn't/didn't happen), 'gal' (put), 'dhad' (send), 'sang' (tell), 'naka' (don't want).
"""

TOPICS = [
    (
        "Bangalore Street Slang & Youth Banter",
        "Generate realistic chats using terms like macha, maga, guru, scene illa, bombat, bekitha, bevarsi, saaku, chindi, sakkat, kirik, meter illa, thale thinbeda, scene aaythu, full tight, swalpa adjust maadi."
    ),
    (
        "Mangalore Coastal College Chat & Slang (Tulu, Konkani, Kanglish)",
        "Generate authentic Mangalore code-switched chats using terms like marre, mandebeccha, banga, malpu, bala, popini, vanas, onas, proxy, clg g, bokka, itte, pokkade, malpodchi, andh marre."
    ),
    (
        "Tulu Daily Greetings & Inquiries",
        "Generate natural Tulu conversations in Latin script: yan ushar ulle, yencha ulla, onas aanda, yenna pudar, dada avondh undu, ninna pudar dada, elle last day atha, yer pura uller."
    ),
    (
        "Mangalorean Catholic Konkani Code-Switched Chat",
        "Generate authentic Mangalorean Konkani WhatsApp chats in Latin script: koso asai, hav boro asa, jevan zale, kale karya, thuka, maka, classik yetai re, zaina anga thavn, salt return evka re."
    ),
    (
        "Food, Darshini, Filter Coffee & Dinner",
        "Generate natural conversations about food, eating out, tea/coffee, snacks, asking if someone had food, restaurant recommendations (oota aitha, thindi aaytha, coffee kudyona, benne dose, biryani tumba chindi, bill split maadona)."
    ),
    (
        "Personal Introductions & Getting to Know People",
        "Generate natural introductory statements and questions: nanna hesaru [name], nanna ooru [place], neevu yavuru, nimma mane elli, nange Kannada swalpa barutthe, nanna brother college ge hogtidane, neevu enu madtidira."
    ),
    (
        "Auto, Cabs, Traffic & Commuting in Karnataka",
        "Generate chats about auto bargaining, traffic jams, metro, booking cabs, asking for routes (meter haaki, ondu vare kodtini, Indiranagar ge hogtira, Silk board traffic, bega baa, cab cancel aaythu)."
    ),
    (
        "WhatsApp / Instagram Daily Conversations with Friends",
        "Generate casual WhatsApp texting among close Kannada/Mangalorean friends: plans, catching up, teasing, laughing, asking where they are, checking in (elli idiya, yavaga barthiya, phone ethu, ondh nimsha iru, photos kalso, call cut aaythu)."
    ),
    (
        "College, Exams, Bunking & Hostel Life",
        "Generate chats between college students about exams, assignments, bunking lectures, semester results, canteen hangout (classes bunk maadona, notes share maado, exam tumba tough itthu, proxy haaku, pass aagbitte)."
    ),
    (
        "Work, Tech Office, Deadlines & Boss/Manager",
        "Generate code-mixed Kanglish conversations about work stress, meetings, client calls, salary, leaves, IT job humor (manager call madtidare, eega busy idini, sprint review aaythu, leave approve aagilla, salary credit aaytha)."
    ),
    (
        "Emotions, Care, Sickness & Personal Advice",
        "Generate emotional and caring conversations: sickness, sympathy, encouragement, family concerns (nange tumba thale novu ide, hushaaraagiru, doctor hathira hogi baa, tumba bejar aagide, relax aagu ellam sari aagutte, thumba thanks guru)."
    ),
    (
        "Phonetic Variations & Chat Texting Habits",
        "Generate sentences demonstrating real texting phonetic variations (hegiddira vs hegideera vs hegdyappa; yenu vs enu; yaavaga vs yavaga; gothilla vs gottilla; aagalla vs agalla; nanna vs nan; nandu vs namdu)."
    ),
    (
        "Disagreements, Arguments & Sharp Retorts",
        "Generate sharp, realistic reactions and retorts (bekitha ninge idhu, sumne iru, nange gothu en madbeku antha, thale kettogide, yake hinge aadtidiya, jasti maatadbeda, bidthira ilva)."
    ),
    (
        "Shopping, Bargaining, Kirana Store & Money",
        "Generate daily shopping, local market bargaining, kirana store chats (yeshtu aaythu anna, swalpa kammi maadi, change illa, online payment madtini, packet haalu kodi, tomato yeshtu rate)."
    ),
    (
        "Casual Questions & Inquiry Phrases",
        "Generate common conversational questions (enu vishesha, yaake barilla, heg ide climate, ivatthu en kelsa, en madtidira, yestu hotthige sigtira, yaru helidhu)."
    )
]

SYSTEM_PROMPT = f"""You are a native linguist specializing in Karnataka languages: Kanglish (Kannada in Latin alphabet), Tulu (in Latin alphabet), and Mangalorean Konkani (in Latin alphabet) as used in WhatsApp, SMS, and casual chat.
Your task is to generate natural, realistic Romanized conversational sentences paired with their accurate, natural English translations.

STRICT GUIDELINES:
1. 'kanglish': Must be written ONLY in Latin/English script (e.g. "nanna hesaru ryan", "yencha ulla marre", "koso asai re", NOT Kannada script, NOT pure English).
2. 'english': Direct, natural, raw English translation capturing the exact intent, colloquial tone, slang, or emotion.
3. Include real chat abbreviations, expressive particles (marre, guru, macha, da, pa, re), and accurate verb endings.
4. Output ONLY valid JSON containing a list of objects with keys: "kanglish" and "english".

{MORPHOLOGY_GUIDE}

REFERENCE GLOSSARY:
{MANGALORE_GLOSSARY_CONTEXT}
"""


def generate_batch(topic_name, topic_prompt, count=8):
    prompt_text = f"""Topic: {topic_name}
Context instruction: {topic_prompt}

Generate exactly {count} distinct, diverse Romanized-to-English translation pairs.
Include short phrases (2-4 words), medium sentences (5-10 words), and conversational questions.
Ensure 100% natural, authentic spoken language in Roman script.

Output format (MUST BE RAW JSON ARRAY OF OBJECTS, NO MARKDOWN, NO CODEBLOCKS):
[
  {{"kanglish": "...", "english": "..."}},
  ...
]
"""
    payload = {
        "contents": [
            {"parts": [{"text": SYSTEM_PROMPT + "\n\n" + prompt_text}]}
        ],
        "generationConfig": {
            "temperature": 0.85,
            "responseMimeType": "application/json",
            "thinkingConfig": {
                "thinkingBudget": 0
            }
        }
    }

    for attempt in range(3):
        try:
            resp = requests.post(API_URL, json=payload, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                pairs = json.loads(raw_text)
                if isinstance(pairs, list):
                    return pairs
            elif resp.status_code == 429:
                print(" [Quota limit, waiting 20s] ", end="", flush=True)
                time.sleep(20)
            else:
                print(f" [HTTP {resp.status_code}] ", end="", flush=True)
        except Exception as e:
            print(f" [Retry {attempt+1}: {e}] ", end="", flush=True)
            time.sleep(5)

    return []


def main(rounds=4):
    print("=" * 60)
    print("GEMINI TEACHER DISTILLATION ENGINE")
    print(f"Teacher Model : {MODEL_NAME}")
    print(f"Target Topics : {len(TOPICS)} categories")
    print(f"Total Batches : {rounds} rounds x {len(TOPICS)} = {rounds * len(TOPICS)} requests")
    print(f"Output File   : {OUTPUT_FILE}")
    print("=" * 60)

    # Load existing to avoid duplicate sentences
    existing_kanglish = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    existing_kanglish.add(obj.get("kanglish", "").strip().lower())
                except:
                    pass
    print(f"Existing teacher pairs: {len(existing_kanglish)}")

    total_new = 0

    for r in range(rounds):
        print(f"\n--- Round {r+1}/{rounds} ---")
        for i, (topic_name, topic_prompt) in enumerate(TOPICS):
            print(f"[{i+1}/{len(TOPICS)}] {topic_name}...", end="", flush=True)
            pairs = generate_batch(topic_name, topic_prompt, count=8)

            new_pairs_for_batch = []
            for p in pairs:
                k = p.get("kanglish", "").strip()
                e = p.get("english", "").strip()
                k_norm = k.lower()
                if k and e and len(k) > 2 and len(e) > 2 and k_norm not in existing_kanglish:
                    existing_kanglish.add(k_norm)
                    new_pairs_for_batch.append({
                        "kanglish": k,
                        "english": e,
                        "topic": topic_name,
                        "teacher": MODEL_NAME
                    })

            # Append immediately to file
            if new_pairs_for_batch:
                with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                    for item in new_pairs_for_batch:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                total_new += len(new_pairs_for_batch)

            print(f" +{len(new_pairs_for_batch)} pairs (Total new: {total_new})", flush=True)
            time.sleep(5)  # Stay strictly under 15 RPM free tier limit

    print("\n" + "=" * 60)
    print(f"[COMPLETE] Distillation finished! Generated {total_new} new pairs.")
    print(f"Saved to: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main(rounds=4)
