"""
scripts/expand_glossary.py
Builds a massive, multi-variant, colloquial and slang glossary for the Android app.
Maps multiple spelling variations to direct, uncensored English meanings.
"""

import json

ENTRIES = [
    # --- Greetings & Checking In ---
    (["hegidya", "hegiddya", "hegidiya", "hegdeya", "hegideeya"], "how are you?"),
    (["hegiddira", "hegideera", "hegidheera"], "how are you? (respectful)"),
    (["chennagi idini", "chennagidini", "chennagiddini", "chennagi idhdhini"], "I am fine / doing well"),
    (["enu samachara", "yenu samachara", "enu samachaara", "yenu samachaara"], "what's the news? / what is up?"),
    (["enu vishaya", "yenu vishaya"], "what is the matter?"),
    (["yenu madtidya", "enu madtidya", "enu madtidiya", "yenu maadtidya", "yenu madthidya"], "what are you doing?"),
    (["guru scene enu", "scene enu guru", "scene enu"], "bro, what's the plan?"),
    (["elli idya", "yelli idya", "elli idiya", "yelli idiya"], "where are you?"),
    (["elli idira", "yelli idira", "elli iddira"], "where are you? (respectful)"),

    # --- Food, Drinks & Daily Life ---
    (["oota aitha", "oota aaytha", "oota aita", "ootaa aithaa", "oota aatha"], "did you eat? / have you eaten?"),
    (["oota maadona", "oota madona", "oota maadana"], "let's eat / let's have lunch/dinner"),
    (["thindi aitha", "thindi aaytha", "tindi aitha", "tindi aaytha"], "did you have breakfast/snacks?"),
    (["coffee aitha", "kaapi aitha", "kaapi aaytha", "coffee aaytha"], "did you have coffee?"),
    (["tea aitha", "tea aaytha"], "did you have tea?"),
    (["malgideya", "malgidya", "nidde bantha", "nidde barthide"], "are you asleep? / feeling sleepy?"),
    (["snana aitha", "snaana aaytha"], "did you have a bath?"),

    # --- Time, Travel & Coordination ---
    (["naale barthini", "naale bartini", "naale barteeni", "naale barteenii"], "I will come tomorrow"),
    (["ivaga barthini", "eega barthini", "ivaga bartini", "eega barteeni", "eegale barthini"], "I am coming right now"),
    (["swalpa wait maadu", "swalpa wait madu", "swalpa thadi", "swalpa thadiyo"], "wait a little"),
    (["begane baa", "begane banni", "fast aagi baa", "speed aagi baa"], "come quickly"),
    (["mane ge hogu", "manege hogu", "manege hogthini", "manege hogtini", "manege hogo"], "go home / I am going home"),
    (["office ge hogbeku", "office ge hogthini", "office ge ಹೊರಟಿದ್ದೀನಿ"], "need to go to office / going to office"),
    (["college ge hogbeku", "college ge hogthini"], "need to go to college"),
    (["jaasthi aithu", "jaasti aaythu"], "it became too much"),
    (["kadime ide", "kammi ide"], "it is less / low"),
    (["yavaga barthiya", "yaavaga bartiya", "yavaga barthidya"], "when will you come?"),

    # --- Common Expressions & Decisions ---
    (["beku", "bekappa"], "want / need"),
    (["beda", "bedappa"], "don't want / no need"),
    (["bekilla", "beke illa", "bekagilla"], "definitely don't need"),
    (["haudu", "houdu", "howdu", "haudu guru"], "yes / that's right / yes bro"),
    (["illa", "ilve illa", "alla"], "no / not at all"),
    (["saaku", "saakappa", "saaku bidi"], "enough / that's enough"),
    (["gothilla", "gottilla", "gothilla guru"], "I don't know"),
    (["gothu", "gottu", "nanage gothu"], "I know"),
    (["tumba thanks", "thumba thanks", "tumba danyavada"], "thanks a lot / thank you very much"),
    (["sumne iru", "sumkire", "sumne iri", "sumne kootko"], "keep quiet / stay calm / sit quietly"),
    (["bega maadu", "bega madu", "jaldi maadu"], "do it quickly"),
    (["kashta ide", "thumba kashta"], "it is difficult"),
    (["sulabha ide", "easy ide"], "it is easy"),
    (["bore hodithide", "tumba bore"], "feeling bored"),
    (["khushi aithu", "khushi aaythu", "tumba khushi"], "very happy"),
    (["tumba bejar aithu", "bejar aaythu"], "feeling very upset / sad"),

    # --- Informal Address & Colloquial Pronouns ---
    (["lo", "ley", "laa"], "hey / dude"),
    (["maga", "mago", "magane"], "dude / bro / son"),
    (["macha", "machan", "machaa"], "buddy / bro"),
    (["guru", "guruve"], "bro / master / mate"),
    (["da", "dostha"], "friend / buddy"),
    (["amma", "amman"], "mother / mom"),
    (["appa", "appaji"], "father / dad"),
    (["anna", "annayya"], "older brother"),
    (["thamma"], "younger brother"),
    (["akka"], "older sister"),
    (["thangi"], "younger sister"),

    # --- Unfiltered Street Slang, Banter & Vulgarities ---
    (["thika mucho", "thika mucchu", "thikka mucho", "thikka mucchu", "thika muchooo", "teeka mucho"], "Shut your ass!"),
    (["lo thika mucho", "ley thika mucho", "lo thikka mucho"], "Hey, shut your ass!"),
    (["thika", "thikka", "teeka"], "ass"),
    (["mucho", "mucchu", "muchhu", "muchooo"], "shut"),
    (["thika uriyuthe", "thikka uriyuthe", "thika uritha ide"], "ass is burning / getting pissed off"),
    (["bolimagne", "boli magne", "bolimakkla", "bole magne"], "son of a bitch"),
    (["sule magne", "soole magne", "sulemagne", "soolemagne"], "son of a whore"),
    (["gandu", "gaandu", "ganduu"], "asshole"),
    (["shata", "shattaa", "shataa"], "bullshit / pubic hair"),
    (["halakat", "halakatte", "halakat nayi"], "scoundrel / bastard / stray dog"),
    (["nin amman", "nin amman thika", "nimmamman thika"], "your mother's ass"),
    (["baddi magne", "baddimagane"], "bastard / rascal"),
    (["keyyu", "keyyoke", "keyyalla"], "fuck / to fuck"),
    (["hogo lo", "hogolo", "hogo ley"], "get lost dude"),
    (["hoge aagbitte", "hoge aithu"], "went up in smoke / completely ruined / dead"),
    (["scene bidthidya", "jaasthi scene bidthiya"], "acting too smart / showing off"),
    (["albedappa", "albedi"], "don't cry")
]

def main():
    flat_list = []
    seen = set()

    # Expand every spelling variation into its own lookup entry
    for variants, english in ENTRIES:
        for v in variants:
            clean_v = v.strip().lower()
            if clean_v not in seen:
                flat_list.append({
                    "kanglish": clean_v,
                    "english": english
                })
                seen.add(clean_v)

    # Sort descending by length so multi-word expressions match first
    flat_list.sort(key=lambda x: len(x["kanglish"]), reverse=True)

    out_path = "mobile/android/app/src/main/assets/glossary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(flat_list, f, indent=2, ensure_ascii=False)

    print(f"Successfully generated {len(flat_list)} comprehensive Kanglish entries into {out_path}!")

if __name__ == "__main__":
    main()
