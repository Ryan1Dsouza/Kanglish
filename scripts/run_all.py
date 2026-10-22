"""
run_all.py – executes prompt variants across qwen2.5:3b and gemma2:2b,
logging to results/log.csv and saving full outputs to results/experiment_details.json.
"""

import csv, datetime, json, os, sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.score import run_evaluation

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

MODELS = ["qwen2.5:3b", "gemma2:2b"]
VARIANTS = [
    "v1_baseline",
    "v2_no_commentary",
    "v3_strong_rules",
    "v4_clean_glossary",
    "v5_fewshot_aligned",
]

def main():
    # Load any already logged runs from results/log.csv
    logged = set()
    log_csv = os.path.join("results", "log.csv")
    if os.path.exists(log_csv):
        import csv
        with open(log_csv, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                logged.add((r["model"], r["prompt_version"]))

    details_path = os.path.join("results", "experiment_details.json")
    all_details = []
    if os.path.exists(details_path):
        try:
            with open(details_path, encoding="utf-8") as f:
                all_details = json.load(f)
        except Exception:
            all_details = []

    for variant in VARIANTS:
        for model in MODELS:
            key = (model, variant)
            if key in logged:
                print(f"Skipping already logged run: model={model}, variant={variant}")
                continue

            print(f"\n==========================================")
            print(f"Running: model={model}, variant={variant}")
            print(f"==========================================")
            result = run_evaluation(model=model, prompt_version=variant, log_to_csv=True)
            all_details.append(result)

            with open(details_path, "w", encoding="utf-8") as f:
                json.dump(all_details, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
