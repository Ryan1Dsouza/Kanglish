"""
scripts/inspect_datasets.py
Inspect and extract samples from Aksharantar (zip) and IN22-Conv (parquet).
Uses only stdlib + pyarrow (for parquet). No model weights downloaded.

Usage:
    python scripts/inspect_datasets.py
    python scripts/inspect_datasets.py --aksharantar
    python scripts/inspect_datasets.py --in22
    python scripts/inspect_datasets.py --sample-n 200
"""

import argparse, csv, hashlib, io, json, os, re, sys, zipfile
from datetime import datetime

# Fix stdout for Kannada script on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

parser = argparse.ArgumentParser(description="Inspect Aksharantar and IN22-Conv datasets")
parser.add_argument("--aksharantar", action="store_true", help="Inspect Aksharantar kan.zip")
parser.add_argument("--in22", action="store_true", help="Inspect IN22-Conv parquet")
parser.add_argument("--sample-n", type=int, default=100, help="Number of rows to write to processed sample")
parser.add_argument(
    "--aksharantar-zip", default="data/raw/aksharantar/kan.zip",
    help="Path to Aksharantar kan.zip"
)
parser.add_argument(
    "--in22-parquet", default="data/raw/in22_conv/in22_conv_mteb_default_test.parquet",
    help="Path to IN22-Conv parquet file"
)
args = parser.parse_args()

# Default: run both if neither flag given
if not args.aksharantar and not args.in22:
    args.aksharantar = True
    args.in22 = True

TIMESTAMP = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_aksharantar(zip_path, sample_n=100):
    print(f"\n{'='*60}")
    print(f"AKSHARANTAR INSPECTION")
    print(f"{'='*60}")

    if not os.path.exists(zip_path):
        print(f"ERROR: {zip_path} not found. Download it first.")
        return None

    size = os.path.getsize(zip_path)
    sha = sha256_file(zip_path)
    print(f"  File: {zip_path}")
    print(f"  Size: {size:,} bytes ({size/1024/1024:.2f} MB)")
    print(f"  SHA-256: {sha}")

    print(f"\n  Archive contents:")
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.namelist()
        for m in members:
            info = zf.getinfo(m)
            print(f"    {m}  ({info.file_size:,} bytes uncompressed)")

        # Aksharantar stores data as JSON inside the zip
        train_member = next((m for m in members if "train" in m.lower() and not m.endswith("/")), None)
        test_member  = next((m for m in members if "test"  in m.lower() and not m.endswith("/")), None)
        valid_member = next((m for m in members if "valid" in m.lower() and not m.endswith("/")), None)

        print(f"\n  Splits found:")
        print(f"    train: {train_member}")
        print(f"    valid: {valid_member}")
        print(f"    test:  {test_member}")

        if not train_member:
            print("  ERROR: No train file found in archive.")
            return None

        # Peek at raw bytes to detect format
        with zf.open(train_member) as raw:
            first_bytes = raw.read(2)
        is_json_array = first_bytes.startswith(b"[")
        is_jsonl = first_bytes.startswith(b"{")
        fmt = "JSON array" if is_json_array else ("JSONL" if is_jsonl else "UNKNOWN")
        print(f"\n  Data format: {fmt}")

        # Count rows and load field names (decompress once per split member)
        print(f"\n  Row counts (parsing full JSON — may take a few seconds):")
        row_counts = {}
        all_data = {}  # split -> list of records (only for train)
        for m in [train_member, valid_member, test_member]:
            if not m:
                continue
            with zf.open(m) as raw:
                content = raw.read().decode("utf-8", errors="replace")
            if is_json_array:
                data = json.loads(content)
            else:
                data = [json.loads(ln) for ln in content.splitlines() if ln.strip()]
            row_counts[m] = len(data)
            if m == train_member:
                all_data["train"] = data
            print(f"    {m}: {len(data):,} records")

        train_data = all_data.get("train", [])
        if not train_data:
            print("  ERROR: Empty train dataset.")
            return None

        first_rec = train_data[0]
        print(f"\n  Field names: {list(first_rec.keys())}")

        # Map to romanized (Latin) and native (Kannada script)
        # Aksharantar format: {"en": "romanized", "kn": "native_script"}
        en_key = next((k for k in first_rec if k.lower() in ("en", "english", "romanized", "english word")), None)
        kn_key = next((k for k in first_rec if k.lower() in ("kn", "kannada", "native", "native word")), None)
        if not en_key or not kn_key:
            keys = list(first_rec.keys())
            en_key = keys[0] if keys else None
            kn_key = keys[1] if len(keys) > 1 else None
        print(f"  Romanized key: '{en_key}',  Native key: '{kn_key}'")

        # Show first 3 records (write to file to handle Kannada script safely)
        print(f"\n  First 3 records:")
        for rec in train_data[:3]:
            print(f"    en={rec.get(en_key,'')!r}  kn=[kannada — written to sample file]")

        # Extract sample
        print(f"\n  Extracting {sample_n}-row sample from train split...")
        sample_rows = []
        seen = set()
        for rec in train_data:
            r = rec.get(en_key, "").strip()
            n = rec.get(kn_key, "").strip() if kn_key else ""
            if r and n and r not in seen:
                seen.add(r)
                sample_rows.append({"romanized_latin": r, "kannada_native": n,
                                    "provenance": "ai4bharat/Aksharantar",
                                    "split": "train",
                                    "license": "CC0-1.0/CC-BY-4.0",
                                    "generation_method": "corpus_mined",
                                    "review_status": "unreviewed",
                                    "notes": "Word-level transliteration pair. NOT a sentence translation."})
            if len(sample_rows) >= sample_n:
                break

        # Write processed sample
        os.makedirs("data/processed/aksharantar", exist_ok=True)
        sample_path = "data/processed/aksharantar/kan_train_sample.csv"
        with open(sample_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(sample_rows[0].keys()), quoting=csv.QUOTE_ALL)
            w.writeheader()
            w.writerows(sample_rows)
        print(f"  Sample written: {sample_path} ({len(sample_rows)} rows, UTF-8 with BOM)")
        print(f"  (Open with Excel or VS Code to view Kannada characters)")

        # Dedup check on romanized keys in sample
        n_dup = len(sample_rows) - len(set(r["romanized_latin"] for r in sample_rows))
        print(f"\n  Deduplication check on sample: {n_dup} duplicate romanized forms")

        return {
            "file": zip_path,
            "size_bytes": size,
            "sha256": sha,
            "members": members,
            "row_counts": row_counts,
            "format": fmt,
            "en_key": en_key,
            "kn_key": kn_key,
            "columns": [en_key, kn_key],
        }






def inspect_in22_conv(parquet_path, sample_n=100):
    print(f"\n{'='*60}")
    print(f"IN22-CONV INSPECTION  (mteb/IN22-Conv)")
    print(f"{'='*60}")

    if not os.path.exists(parquet_path):
        print(f"ERROR: {parquet_path} not found.")
        return None

    try:
        import pyarrow.parquet as pq
    except ImportError:
        print("ERROR: pyarrow not installed. Run: pip install pyarrow")
        return None

    size = os.path.getsize(parquet_path)
    sha = sha256_file(parquet_path)
    print(f"  File: {parquet_path}")
    print(f"  Size: {size:,} bytes ({size/1024/1024:.2f} MB)")
    print(f"  SHA-256: {sha}")

    table = pq.read_table(parquet_path)
    n_rows = table.num_rows
    columns = table.schema.names
    print(f"\n  Total rows: {n_rows:,}")
    print(f"  Total columns: {len(columns)}")
    print(f"  Columns: {', '.join(columns)}")

    # Confirm Kannada and English columns present
    assert "kan_Knda" in columns, "MISSING kan_Knda column!"
    assert "eng_Latn" in columns, "MISSING eng_Latn column!"
    print(f"\n  Key columns confirmed: kan_Knda (Kannada), eng_Latn (English)")

    # Duplicate check on kan_Knda
    kan_col = table.column("kan_Knda").to_pylist()
    eng_col = table.column("eng_Latn").to_pylist()
    n_null_kan = sum(1 for v in kan_col if not v or not v.strip())
    n_null_eng = sum(1 for v in eng_col if not v or not v.strip())
    n_dup_kan = n_rows - len(set(kan_col))
    n_dup_pairs = n_rows - len(set(zip(kan_col, eng_col)))
    print(f"\n  Quality checks:")
    print(f"    Null/empty kan_Knda: {n_null_kan}")
    print(f"    Null/empty eng_Latn: {n_null_eng}")
    print(f"    Duplicate kan_Knda rows: {n_dup_kan}")
    print(f"    Duplicate (kan,eng) pairs: {n_dup_pairs}")

    # Show 5 samples
    print(f"\n  Sample rows (first 5):")
    for i in range(min(5, n_rows)):
        print(f"\n  Row {i}:")
        print(f"    kan_Knda : {kan_col[i]}")
        print(f"    eng_Latn : {eng_col[i]}")

    # Write processed sample with provenance fields
    os.makedirs("data/processed/in22_conv", exist_ok=True)
    sample_path = "data/processed/in22_conv/in22_conv_kan_en_sample.csv"
    sample_rows = []
    for i in range(min(sample_n, n_rows)):
        sample_rows.append({
            "source_row_index": i,
            "kannada_native": kan_col[i],
            "english_reference": eng_col[i],
            "source_dataset": "mteb/IN22-Conv",
            "source_split": "test",
            "license": "CC-BY-4.0",
            "provenance": "in22_conv_derived",
            "generation_method": "corpus_transliterated",
            "review_status": "unreviewed",
            "notes": "Native Kannada script. Requires transliteration to Kanglish for training use.",
        })

    with open(sample_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(sample_rows[0].keys()), quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(sample_rows)
    print(f"\n  Sample written: {sample_path} ({len(sample_rows)} rows)")

    # Duplicate check in sample
    dup_check = {}
    for r in sample_rows:
        key = r["kannada_native"]
        if key in dup_check:
            print(f"  WARNING: Duplicate Kannada text at rows {dup_check[key]} and {r['source_row_index']}")
        dup_check[key] = r["source_row_index"]
    print(f"  Deduplication check complete: {n_dup_kan} duplicates in full dataset")

    return {
        "file": parquet_path,
        "size_bytes": size,
        "sha256": sha,
        "total_rows": n_rows,
        "columns": columns,
        "null_kan": n_null_kan,
        "null_eng": n_null_eng,
        "dup_kan": n_dup_kan,
    }


# ── Run ───────────────────────────────────────────────────────────────────────
results = {}

if args.aksharantar:
    r = inspect_aksharantar(args.aksharantar_zip, args.sample_n)
    if r:
        results["aksharantar"] = r

if args.in22:
    r = inspect_in22_conv(args.in22_parquet, args.sample_n)
    if r:
        results["in22_conv"] = r

print(f"\n{'='*60}")
print(f"INSPECTION COMPLETE  ({TIMESTAMP})")
print(f"{'='*60}")
for name, r in results.items():
    print(f"  {name}: {r.get('size_bytes',0):,} bytes, sha256={r.get('sha256','N/A')[:16]}...")
