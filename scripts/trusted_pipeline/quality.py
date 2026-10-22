"""Structural training safeguards. Passing these checks is not semantic review."""

from collections import defaultdict
import hashlib
import re
import unicodedata

KANNADA = re.compile(r"[\u0c80-\u0cff]")


def english_target_issue(value):
    if not isinstance(value, str) or not value.strip():
        return "empty_or_non_text_target"
    if value.lstrip().startswith(("=", "→", "->")):
        return "unresolved_dictionary_reference"
    if KANNADA.search(value):
        return "kannada_in_english_target"
    if not re.search(r"[A-Za-z]", value):
        return "no_english_letters"
    return None


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def variant_key(value):
    """Conservative split grouping only; never replaces the actual input text."""
    value = normalized(value)
    value = "".join(c if unicodedata.category(c)[0] in "LMN" else " " for c in value)
    value = re.sub(r"([a-z])\1+", r"\1", value)
    return " ".join(value.split())


def training_pair(record):
    messages = record.get("messages", [])
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")
    roles = [m.get("role") for m in messages if isinstance(m, dict)]
    if roles != ["system", "user", "assistant"]:
        raise ValueError("expected exactly system, user and assistant messages")
    if any(not isinstance(m.get("content"), str) or not m["content"].strip() for m in messages):
        raise ValueError("message content must be nonempty text")
    return messages[1]["content"], messages[2]["content"]


def assert_clean_training_records(records):
    if not records:
        raise ValueError("Training data is empty")
    issues = []
    for index, record in enumerate(records, 1):
        try:
            _, target = training_pair(record)
            issue = english_target_issue(target)
        except (ValueError, AttributeError, TypeError) as exc:
            issue = str(exc)
        if issue:
            issues.append((index, issue))
    if issues:
        raise ValueError(f"Training data rejected: {len(issues)} invalid rows; first issues: {issues[:5]}. "
                         "Use scripts/prepare_quality_dataset.py to create a separate cleaned candidate export.")


def stable_rank(value, seed=42):
    return hashlib.sha256(f"{seed}|{value}".encode("utf-8")).hexdigest()


def balanced_lexicon_sample(rows, limit=2500, seed=42):
    """Sample throughout the lexicon, keeping a comparable share per initial.

    Restrict to existing ASCII phonetic forms; no new Romanizations or meanings
    are invented. Different meanings of the same input are excluded for review.
    """
    if limit < 0:
        raise ValueError("limit must be nonnegative")
    by_input = defaultdict(dict)
    for row in rows:
        source = row.get("original_kanglish", "").strip()
        target = row.get("english_meaning", "").strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z '\-]*", source):
            continue
        if english_target_issue(target) or len(target) >= 80:
            continue
        by_input[normalized(source)].setdefault(normalized(target), row)
    buckets = defaultdict(list)
    for source, meanings in by_input.items():
        if len(meanings) == 1:
            buckets[source[0]].append(next(iter(meanings.values())))
    for bucket in buckets.values():
        bucket.sort(key=lambda r: stable_rank(r.get("entry_id", "") + "|" + normalized(r["original_kanglish"]), seed))
    result, offset = [], 0
    while len(result) < limit:
        added = False
        for initial in sorted(buckets):
            if offset < len(buckets[initial]):
                result.append(buckets[initial][offset])
                added = True
                if len(result) == limit:
                    break
        if not added:
            break
        offset += 1
    return result


def grouped_split(records, validation_fraction=0.1, seed=42):
    """Keep source siblings, normalized spelling variants and shared answers together.

    This is an internal development split, not a human-reviewed quality benchmark.
    """
    if not 0 < validation_fraction < 1:
        raise ValueError("validation fraction must be between zero and one")
    parents = list(range(len(records)))

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left, right):
        left, right = find(left), find(right)
        if left != right:
            parents[max(left, right)] = min(left, right)

    seen, keys_by_row = {}, []
    for index, row in enumerate(records):
        source, target = training_pair(row)
        keys = ["input:" + variant_key(source), "answer:" + variant_key(target)]
        if row.get("group_id"):
            keys.append("source:" + row["group_id"])
        keys_by_row.append(keys)
        for key in keys:
            if key in seen:
                union(index, seen[key])
            else:
                seen[key] = index
    groups = defaultdict(list)
    for index in range(len(records)):
        groups[find(index)].append(index)
    training, validation = [], []
    for indices in groups.values():
        identity = min(key for index in indices for key in keys_by_row[index])
        bucket = int(stable_rank(identity, seed), 16) / (1 << 256)
        destination = validation if bucket < validation_fraction else training
        destination.extend(records[index] for index in indices)
    for split in (training, validation):
        split.sort(key=lambda r: stable_rank("|".join(training_pair(r)), seed))
    if not training or not validation:
        raise ValueError("The grouped split is empty on one side; choose more data or a different seed/fraction")
    return training, validation
