"""Conservative data checks and documented metrics, all Python standard library."""
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import hashlib
import re
import unicodedata

KAN = re.compile(r"[\u0c80-\u0cff]")
NEG_EN = re.compile(r"\b(?:no|not|never|without|cannot|neither|nor)\b|n['’]t\b", re.I)
NEG_ROM = re.compile(r"\b(?:[a-z]*(?:alla|illa)|beda|bedi|beDa|agalla|aagalla|baralla|madabeda|maadabedi)\b", re.I)
TIME_WORDS = {"naale": "tomorrow", "nale": "tomorrow", "ivattu": "today", "ivathu": "today", "ninne": "yesterday"}
STOP_NAMES = set("I A An The This That These Those It He She We You They My Your His Her Our Their There Here Please Yes No What When Where Why How Which Who Can Could Will Would Should Do Does Did Is Are Was Were Be Have Has Had Open Close Send Show Find Get Give Take Tell Set Play Search Turn Add Call Read Delete Remove Make Put Let And Or But On In At To For From By With Of As All Any Some Every Next Last New Today Tomorrow Yesterday Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August September October November December English Kannada India Indian Google YouTube WhatsApp Facebook Amazon Twitter Internet Modi".lower().split())

def normalized(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join("".join(c if unicodedata.category(c)[0] in "LMN" else " " for c in text).split())

def compact(text):
    return normalized(text).replace(" ", "")

def family_key(text):
    return re.sub(r"([a-z])\1+", r"\1", compact(text)).replace("ph", "f")

def rank(value, seed=42):
    return hashlib.sha256(f"{seed}|{value}".encode()).hexdigest()

def number_tokens(text):
    text = "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)
    return Counter(re.findall(r"\d+(?:[.,]\d+)*", text))

def names_in_reference(text, name_vocabulary=()):
    tokens = re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*", text)
    names = {t.lower() for t in tokens if t.lower() in name_vocabulary}
    names.update(t.lower() for i, t in enumerate(tokens) if i > 0 and t[0].isupper() and t.lower() not in STOP_NAMES)
    return sorted(names)

def name_preserved(name, source):
    words = normalized(source).split()
    n = family_key(name)
    return any(n == family_key(w) or (len(n) >= 4 and SequenceMatcher(None, n, family_key(w), autojunk=False).ratio() >= .8) for w in words)

def row_issues(source, english, category, names=(), latin_spans=(), parent_source=None):
    reasons = []
    if not source.strip() or not english.strip(): reasons.append("empty_text")
    if KAN.search(source): reasons.append("unromanized_input")
    if KAN.search(english): reasons.append("kannada_in_english_target")
    if english.lstrip().startswith(("=", "->", "→")): reasons.append("dictionary_pointer")
    if category == "abstention":
        if english != "[unclear]": reasons.append("invalid_abstention_target")
        return reasons
    if number_tokens(source) != number_tokens(english): reasons.append("number_mismatch")
    base = parent_source or source
    if category != "dictionary":
        source_neg = bool(NEG_ROM.search(base))
        target_neg = bool(NEG_EN.search(english))
        if source_neg != target_neg: reasons.append("negation_review")
        # bidi can mean 'leave/let'; it is not automatically labelled a negative.
        if re.search(r"\bbidi\b", base, re.I): reasons.append("ambiguous_bidi_review")
        source_words = set(normalized(base).split())
        for word, meaning in TIME_WORDS.items():
            if word in source_words and not re.search(r"\b" + meaning + r"\b", english, re.I):
                reasons.append("time_word_mismatch:" + meaning)
        for name in names:
            if not name_preserved(name, base): reasons.append("name_mismatch:" + name)
        for span in latin_spans:
            if span.casefold() not in source.casefold(): reasons.append("latin_span_changed:" + span)
    return sorted(set(reasons))

class FuzzyIndex:
    """Candidate retrieval by character bigrams; final comparisons use full strings.

    Ratios are difflib Ratcliff/Obershelp, not an unreported edit-distance metric.
    Compact forms catch spacing; folded forms catch repeated vowels and ph/f.
    """
    def __init__(self, threshold=.88, short_edits=True):
        self.threshold = threshold
        self.short_edits = short_edits
        self.values = []
        self.meta = []
        self.exact = defaultdict(list)
        self.folded = defaultdict(list)
        self.grams = defaultdict(set)
        self.gram_counts = []
        self.folds = []
        self.short_deletions = defaultdict(set)

    def add(self, value, metadata):
        value = compact(value)
        if not value: return
        idx = len(self.values)
        self.values.append(value); self.meta.append(metadata)
        self.exact[value].append(idx)
        self.folded[family_key(value)].append(idx)
        self.folds.append(family_key(value))
        counts=Counter(value[i:i+2] for i in range(max(0,len(value)-1)))
        self.gram_counts.append(counts)
        for gram in counts:self.grams[gram].add(idx)
        if self.short_edits and 4<=len(value)<=10:
            for key in {value}|{value[:i]+value[i+1:] for i in range(len(value))}:
                self.short_deletions[key].add(idx)

    def matches(self, value, all_matches=False):
        value = compact(value)
        if not value: return []
        folded=family_key(value)
        candidates = set(self.exact.get(value, [])) | set(self.folded.get(folded, []))
        direct=set(candidates)
        short_candidates=set()
        if self.short_edits and 4<=len(value)<=10:
            for key in {value}|{value[:i]+value[i+1:] for i in range(len(value))}:
                short_candidates.update(self.short_deletions.get(key,()))
            candidates.update(short_candidates)
        gram_counts = Counter()
        qgrams = Counter(value[i:i+2] for i in range(max(0, len(value)-1)))
        for gram,count in qgrams.items():
            for idx in self.grams.get(gram,()):
                target_length=len(self.values[idx])
                if 2*min(len(value),target_length)/(len(value)+target_length)>=self.threshold:
                    gram_counts[idx]+=min(count,self.gram_counts[idx][gram])
        # Safe necessary bound: with M matched characters and U unmatched characters,
        # there are at most U+1 matching blocks, hence >= M-U-1 shared bigrams.
        # ratio >= t requires shared bigrams >= (1.5*t-1)*(len(a)+len(b))-1.
        candidates.update(idx for idx,count in gram_counts.items()
            if count+1e-8 >= (1.5*self.threshold-1)*(len(value)+len(self.values[idx]))-1)
        found = []
        for idx in sorted(candidates):
            target = self.values[idx]
            if idx in direct or value == target or folded == self.folds[idx]:
                ratio = 1.0; kind = "normalized_or_spelling_family"
            else:
                if idx in short_candidates:
                    from .contract import within_one_edit
                    if within_one_edit(value,target):
                        found.append({'match':self.meta[idx],'ratio':round(SequenceMatcher(None,value,target,autojunk=False).ratio(),4),'kind':'short_edit_distance_1'})
                        if not all_matches:return found
                        continue
                if 2 * min(len(value), len(target)) / (len(value)+len(target)) < self.threshold: continue
                match = SequenceMatcher(None, value, target, autojunk=False)
                if match.quick_ratio() < self.threshold: continue
                ratio = match.ratio(); kind = "fuzzy"
                if ratio < self.threshold: continue
            found.append({"match": self.meta[idx], "ratio": round(ratio, 4), "kind": kind})
            if not all_matches: return found
        return found

def chrf_stats(prediction, reference, order=6):
    hyp = "".join(prediction.split()); ref = "".join(reference.split())
    stats = []
    for n in range(1, order+1):
        h = Counter(hyp[i:i+n] for i in range(max(0, len(hyp)-n+1)))
        r = Counter(ref[i:i+n] for i in range(max(0, len(ref)-n+1)))
        stats.append((sum(h.values()), sum(r.values()), sum((h & r).values())))
    return stats

def chrf_score(stats, beta=2):
    eligible = [(h, r, m) for h, r, m in stats if h > 0 and r > 0]
    if not eligible: return 0.0
    p = sum(m/h for h, r, m in eligible)/len(eligible)
    r = sum(m/r for h, r, m in eligible)/len(eligible)
    return 100*(1+beta*beta)*p*r/(beta*beta*p+r) if p+r else 0.0

def metric_summary(rows):
    scored = [r for r in rows if r.get("english") and r.get("category") != "abstention"]
    stats = [[0,0,0] for _ in range(6)]
    for row in scored:
        for dest, src in zip(stats, chrf_stats(row.get("output", ""), row["english"])):
            for i in range(3): dest[i] += src[i]
    dictionary = [r for r in scored if r.get("category") == "dictionary"]
    negative = [r for r in rows if r.get("category") == "abstention"]
    real = [r for r in rows if r.get("category") != "abstention"]
    number_rows = [r for r in scored if number_tokens(r["english"])]
    names = [(r, n) for r in scored for n in r.get("names", [])]
    neg_errors = sum(bool(NEG_EN.search(r.get("output", ""))) != bool(NEG_EN.search(r["english"])) for r in scored)
    return {"cases":len(rows), "operational_failures":sum(r.get("status") != "ok" for r in rows),
        "chrf2":round(chrf_score(stats),4), "chrf_reference_rows":len(scored),
        "dictionary_exact_matches":sum(r.get("output", "").strip().casefold() == r["english"].strip().casefold() for r in dictionary),
        "dictionary_rows":len(dictionary),
        "number_preserved":sum(number_tokens(r.get("output", "")) == number_tokens(r["english"]) for r in number_rows),
        "number_eligible":len(number_rows),
        "name_preserved":sum(name_preserved(n,r.get("output", "")) for r,n in names),"name_eligible":len(names),
        "negation_polarity_errors":neg_errors,"negation_eligible":len(scored),
        "negative_control_abstentions":sum(r.get("output", "").strip()=="[unclear]" for r in negative),
        "negative_controls":len(negative),
        "false_abstentions_real":sum("[unclear]" in r.get("output", "").lower() for r in real),
        "real_inputs":len(real)}
