import csv, json, sys, urllib.request

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:3b"

SYSTEM = """You decode Kanglish: Kannada written in English letters, mixed with English, as used in college WhatsApp group chats. Spelling varies a lot. Reply with ONLY the natural English meaning, in one line."""

SHOTS = """Kanglish: eno maadtidya?
English: What are you doing?

Kanglish: nanna jothe bartiya?
English: Will you come with me?

Kanglish: oota aitha?
English: Did you eat?

"""

def ask(text, context):
    prompt = SYSTEM + "\n\n" + SHOTS
    if context:
        prompt += f"Previous message: {context}\n"
    prompt += f"Kanglish: {text}\nEnglish:"
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request("http://localhost:11434/api/generate", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())["response"].strip()

with open("data/test.csv", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        print("IN :", row["kanglish"])
        print("EXP:", row["english"])
        print("GOT:", ask(row["kanglish"], row["context"]))
        print()
