# Kanglish student repair: Gate A report

Generated 2026-10-19T12:53:20.704830+00:00. **Stopped at Gate A. Training is not authorized yet.**

The v3 model produced the required abstention on 0/51 negative controls. It still invents translations for gibberish and reverses meaning on some real Kannada inputs. The prepared data is a candidate repair, not evidence of an improved student.

Phase 0 evaluation: complete. Post-export verification: **PASS**. Phase B training, Gate B comparison, Phase C quantization and device measurements have not run. The user imposed a 10-minute finalization limit ending at 2026-10-19 12:55:32 UTC.

[Review sample: 200 translation rows and 50 abstention rows](../data/processed/student_gate_a_v1/review_sample.csv). [Quarantined candidates](../data/processed/student_gate_a_v1/review_queue.csv). [Data manifest](../data/processed/student_gate_a_v1/manifest.json).

A Kannada-fluent reviewer must mark exactly one of `ok` or `wrong` for every sample row and add corrections in `notes`. Use `1`, `yes`, or `x` as a mark. Keep source and English columns intact. The checker requires at most 10% wrong in each section (at most 20/200 translation rows and 5/50 abstention rows). Your explicit confirmation is still required after the review passes. No candidate has been used to train a student.

**Current v3 Q8_0 baseline**

| Suite | Cases | chrF2 | Negation polarity mismatches | Operational failures |
|---|---:|---:|---:|---:|
| [Draft benchmark](../results/student_gate_a_20261019/baseline_benchmark_current/app_visible_metrics.json) | 100/100 | 33.26 | 19/100 | 0 |
| [IN22-Conv Romanized](../results/student_gate_a_20261019/baseline_in22/app_visible_metrics.json) | 1503/1503 | 15.71 | 277/1503 | 22 |
| [Dictionary holdout](../results/student_gate_a_20261019/baseline_dictionary/app_visible_metrics.json) | 100/100 | 4.76 | 5/100 | 0 |
| [Controls and known failures](../results/student_gate_a_20261019/baseline_controls/app_visible_metrics.json) | 54/54 | 32.80 | 1/3 | 0 |

| Suite | Dictionary exact match | Number preservation | Name preservation |
|---|---:|---:|---:|
| Draft benchmark | N/A | N/A | N/A |
| IN22-Conv Romanized | N/A | 5/83 (6.0%) | 102/643 (15.9%) |
| Dictionary holdout | 0/100 (0.0%) | N/A | N/A |
| Controls and known failures | 0/1 (0.0%) | N/A | N/A |

Negative-control abstention: **0/51**. False abstention on real inputs: **0/1706**. Zero false abstentions is not useful reassurance when the model never abstains.

chrF2 uses character orders 1–6, beta=2, case-sensitive text, and excludes whitespace. The controls/failures chrF2 score covers only its three real inputs. Negation checks compare explicit English polarity markers; names use heuristic extraction and spelling matching. Number preservation compares numeric tokens, so spelled-out numbers can fail this diagnostic. These are diagnostics, not Kannada-speaker semantic accuracy. The draft benchmark and dictionary sample are unreviewed. IN22 English references are human translations, but their Romanization is machine-generated. Operational failures stay in the saved predictions and metrics. For the reported app-visible metrics, failed generations are scored as empty translations because Android rejects partial outputs. The original metrics.json files preserve raw-candidate scores (IN22 chrF2 15.7252), including partial text from 22 output-limit failures. Use app_visible_metrics.json and the same failure policy for subsequent student comparisons.

| Requested input | Reference | v3 output |
|---|---|---|
| marmarisu | to make a sound by shaking leaves or by walking on dry leaves. | margarine |
| naanu baralla ivattu | I will not come today | I will come today |
| naale college ge barthira | Are you coming to college tomorrow? | I will come to college tomorrow |
| zqxvpl | [unclear] | hey |

Every suite folder contains `predictions.jsonl`, `metrics.json`, `config.json`, `worst_30.json`, and a source snapshot. All inference used the unchanged GGUF through local Ollama 0.23.2, raw ChatML, the app glossary route, temperature 0.1, seed 42, context 1024 and a 192-token response cap. History and learned glossary were empty. No external model API calls, paid services, or private chats were used.

Median desktop model-route wall time: 339.6 ms. Token precheck matched runtime prompt counts on 1757/1757 recorded cases. This is not an Android/S23 FE latency or runtime-parity measurement.

An independent workspace edit changed `TranslationPrompt.kt` during preparation. The current baseline and candidate prompts use the new time/negation hints; their frozen prompt SHA256 is `38942163eb1e650f75806461cb6fdf45ea7b1c146708fe468cc9763d339ab803`. The earlier `baseline_benchmark` run used the older prompt and is superseded. This task made no Android feature or audio-roadmap edits.

**Candidate data**

| Category | Training candidates | Validation candidates |
|---|---:|---:|
| conversation | 6,473 | 663 |
| dictionary | 910 | 90 |
| abstention | 222 | 28 |
| Total | 7,605 | 781 |

Conversation targets are copied verbatim from BPCC-H human translations; source IDs from `quality_v1` are tracked. Kannada inputs were Romanized with pretrained AI4Bharat IndicXlit, followed by 3–5 spelling variants plus the base input. English/Latin spans, detected names, time words and negation markers are protected. Duplicate variants are removed. Dictionary targets are short authored Alar senses with unresolved references excluded; they are review candidates. Before training, dictionary senses must meet the user’s reviewed-sense requirement; a passing random sample alone is not row-level review of every sense.

Dictionary coverage: 1,000 entries across 21 initials (47–48 each). 988 entries occur at most once in Aksharantar native training words. This is a rarity proxy, not confirmation that each word is rare. Real words retain their normal dictionary target.

The 250 abstention candidates map only to `[unclear]` and were absent from 156,620 Alar entries, 489 glossary entries, and Aksharantar train/validation/test inventories (2,906,728 / 7,025 / 11,380 rows). Inventory absence cannot establish absence from all Kannada words or names. No mixed partial-abstention sentences were fabricated; none had reviewer-confirmed references.

Each row records source group, source ID/provenance and license. Conversation references come from `data/trusted/conversational_bpcc.csv`; dictionary senses come from `data/trusted/lexicon_alar.csv`. Synthetic controls record `project_generated_candidate`. See the JSONL provenance fields for upstream attribution and URLs.

Source groups and spelling families are kept in one split. Benchmark, IN22, dictionary holdout, requested failures and other reserved cases are excluded using normalized inputs, native text and English references. The fuzzy guard uses SequenceMatcher >=0.88, compact/repeated-letter/ph-f families, and edit distance <=1 for strings of length 4–10. This is the implemented near-duplicate definition; it is not a semantic-paraphrase detector.

Review queue: 3,085 distinct queued records: 2,782 BPCC, 38 dictionary and 265 historical teacher candidates. Historical teacher outputs are review candidates only. No new teacher output was generated. Some BPCC pairs localize people’s names, including Bhuvana/George and Modi/Trump; suspected mismatches were quarantined without changing the human English text.

| Rejection reason | Reason events |
|---|---:|
| name_mismatch | 4,796 |
| negation_review | 88 |
| unromanized_input | 126 |
| fewer_than_three_safe_spelling_variants | 130 |
| number_mismatch | 27 |
| time_word_mismatch | 12 |
| evaluation_near_duplicate | 37 |
| ambiguous_bidi_review | 1 |
| teacher_output_requires_kannada_review | 265 |

Rejection counts are reason events and must not be added as distinct rejected rows. Selection caps were 1,500 conversation source groups and 1,000 dictionary entries. No rows were padded to reach a target.

**Verification and reproducibility limits**

Nine targeted tests passed: prompt and glossary contract, fuzzy-index candidate coverage, short-typo detection, one-edit distance, structural quarantine rules, protected spelling variants and chrF identity/no-overlap. No Android build was required because this task did not edit Android code.

Independent post-export verification: **PASS**. [Full verification evidence](../results/student_gate_a_20261019/dataset_verification.json).

Checked 8,386 rows; 0 recorded errors; 0 cross-split spelling-variant matches. Source-group overlap: 0. Protected evaluation/data hashes unchanged: True.

IndicXlit uses the official pretrained indic-en v1.0 tensors through a local PyTorch adapter: all 263 learned tensors were mapped, with no trained replacement weights. Decoding is greedy with a Latin/EOS mask and no frequency rescoring. Independent numerical parity with the original Fairseq runtime has not been established. The 12,274-token cache had no unknown input characters or incomplete generations, but that does not prove correct Romanization. The Kannada reviewer must check spelling variants and meanings.

Baseline GGUF: 531,067,840 bytes (506.47 MiB), SHA256 `ce172bdd5f50f6a65547c7b05268ea982674efb33795a2fbcd21f2d73e75ea1a`. Model: Qwen2.5-0.5B v3 Q8_0, local name `kanglish-gate-v3-q8:latest`. App llama.cpp revision: `5aeac37a35b44fde4bdffaec9159f2fcb253b622`. [Environment versions](../results/student_gate_a_20261019/environment.json). [Candidate configuration](../data/processed/student_gate_a_v1/config.json). Seeds are 42. No API keys are needed.

**Reproduction commands**

Run from the repository root using the existing pinned source corpus files and model/tokenizer assets. The public IndicXlit download uses no inference API. Commands below use new output folders so saved evidence is preserved. Ollama must already be serving locally. The baseline runner checks the GGUF hash and freezes configuration.

```powershell
python -B -m scripts.student_pipeline.download_assets
python -B -u -m scripts.student_pipeline.indicxlit_runtime --out results/student_gate_a_repro/romanization_cache.jsonl --batch-size 96
python -B -u -m scripts.student_pipeline.data freeze --run results/student_gate_a_repro --cache results/student_gate_a_repro/romanization_cache.jsonl --seed 42
python -B -u -m scripts.student_pipeline.data prepare --run results/student_gate_a_repro --cache results/student_gate_a_repro/romanization_cache.jsonl --out data/processed/student_gate_a_repro --seed 42 --max-sentences 1500 --max-dictionary 1000
Copy-Item -LiteralPath results/student_gate_a_20261019/protected_hashes_before.json -Destination results/student_gate_a_repro/protected_hashes_before.json
python -B -u -m scripts.student_pipeline.verify --run results/student_gate_a_repro --data data/processed/student_gate_a_repro
ollama create kanglish-gate-v3-q8 -f results/audit_20261019/Modelfile.v3
python -B -u -m scripts.student_pipeline.evaluate --cases results/student_gate_a_repro/evaluation/benchmark.jsonl --out results/student_gate_a_repro/baseline_benchmark --max-seconds 1800
python -B -u -m scripts.student_pipeline.evaluate --cases results/student_gate_a_repro/evaluation/in22.jsonl --out results/student_gate_a_repro/baseline_in22 --max-seconds 1800
python -B -u -m scripts.student_pipeline.evaluate --cases results/student_gate_a_repro/evaluation/dictionary.jsonl --out results/student_gate_a_repro/baseline_dictionary --max-seconds 1800
python -B -u -m scripts.student_pipeline.evaluate --cases results/student_gate_a_repro/evaluation/controls_and_failures.jsonl --out results/student_gate_a_repro/baseline_controls --max-seconds 1800
python -B -m unittest tests.test_student_gate_pipeline -v
python -B -m scripts.student_pipeline.data review-status --out data/processed/student_gate_a_v1
python -B -m scripts.student_pipeline.report
```

The preparation commands refuse to overwrite an existing candidate export. Resume an incomplete evaluation by repeating the same command; changed inputs, prompt, model or evaluator code cause it to refuse. Source corpus acquisition is not rerun by these commands; their existing row provenance and checksums are retained. The report command reads this dated run, while the other example commands build the separate reproduction run.

**Thirty lowest-chrF baseline outputs**

Ranked by sentence chrF2, with ties sorted by case ID. This is a diagnostic ranking, not human severity judgment. [Full rows and metadata](../results/student_gate_a_20261019/baseline_worst_30.json).

| ID | Input | Reference | Output | chrF2 |
|---|---|---|---|---:|
| IN22-0150 | innu eradnedu, ibru hindugalaagiddaaga anvayisontha kayde, adu jainaru, bouddharu mattu sikkharigoo anvayisatte. | The latter is an act for two Hindus, extending to Jains, Buddhists and Sikhs. |  | 0.00 |
| IN22-0183 | idra vishyadalloo neevu husharagiri, yakandre nimma bhaaratiya veesa processes aagi anumati sikmele adanna neevu niididantha imail vilaasakke neravagi kaluhisalaagatte. | Please be careful about this too, as when an Indian visa has been processed and approved, it will be sent directly to the email address given on the application. |  | 0.00 |
| IN22-0237 | naavu ganga nadiyinda praarambhisidvi, idanna ganges antloo kareetaare, idu bhaaratada athi uddada nadiyagide, idakke dhaarmikavaagi tumbane mahatva ide, aadre idelladra jotege, adu atyanta malinavagiro nadigalalloo ondaagide. | We started with the river Ganga, also called Ganges, which is the longest river of India, it has a lot of religious significance, but at the same time, it is also one of the highly polluted rivers. |  | 0.00 |
| IN22-0463 | neevu premiyamna pratee tinglu, mooru tingligomme, aaru tingligomme athwa varshakkondsala anta tumbisbahudu. | You can pay the premium monthly, quarterly, six-monthly or annually. |  | 0.00 |
| IN22-0571 | halavaaru adhyayanagala prakaara, pratyakshavagi shaastriya sangeetavanna kelodu makkalalli sakaaraatmaka bhavanegalanna moodsatte. | According to studies, listening to live classical music evokes positive feelings in children. |  | 0.00 |
| IN22-0573 | shaastriya sangeeta makkala belavanigeya mele olle parinama biratte antaytu, sarrie olledu. | Classical music is beneficial to children's development, that's nice. |  | 0.00 |
| IN22-0651 | swalpa vyatyaasa ide anta nangartha aagatte, aadre neenu kelavondu aayda vishyagala bagge kelavu videogalanna nodo prayatna maadu, adoo ninge ondu chitranavanna kattikodatte. | I can understand that it is a bit dfferent, but you can try watching a few videos for some selective topics, that also gives an idea. |  | 0.00 |
| IN22-0661 | udaaharanege, himalaya parvatashrenigalne togo, adanna bere bere rajyagalinda nodbahudu, ananyavaaddu adu, kanchanagange matte adhe thara innoo sumaarive, nododakke prati shreninoo tannade aada vaishishtyagalanna hondiratte. | Like take for example the different Himalayan ranges which you can see from different states like Kanchenjunga, and many more are there, is one of a kind and each range have it's own feature to share. |  | 0.00 |
| IN22-0791 | apayasuchaka pramaanadalli malinya hechchagtirodrinda, naavu bhoomigaagi andaju moorane ondu bhagadashtu amlajanakavanna yaavudu utpadista idyo adara samrakshane madbekirodu atyagatyavagide. | Given the alarming rates of increasing pollution, it's essential that we conserve what produces roughly one-third of the oxygen for the planet. |  | 0.00 |
| IN22-0853 | adanna kempakki, belekaalugala tari mattu hasi parangikayiya mishranavanna balsi tayaaristaare, haagaagi adu sampoorna sasyahari tinisu. | It is made of a mix of red rice, beaten pulses and raw papaya so it is completely vegetarian. |  | 0.00 |
| IN22-0899 | hechchu samayavenu agolla, bunny surr, neevu aaa reeti dakhalegalanna kalisidre avu bere arjigala jote serihogbahudu. | Sir, it won't take much time, sending the documents might get mixed with the other applications. |  | 0.00 |
| IN22-1066 | alli aaru vibhagagalive, sarjanaatmaka mattu vaignaanika kalakritigalanna hondiro aidu pradarshana mandiragalive, avu yavuvandre puratattva shaastra, bhuvijnaana, arthashaastra, soundarya mattu kale. | It possesses six sections containing five galleries of creative and scientific work of art that are archaeology, geology, economic beauty, and art. |  | 0.00 |
| IN22-1099 | kaavya prakaaradalli samskruta krutigala nirantara harivina jadanna jagatika saahityada atyanta haleya daakhaleyaada rugvedadavaregu gurutisbahudaagide. | A continuous flow of Sanskrit works in poetry can be traced back to the Rigveda, the oldest document in world literature. |  | 0.00 |
| IN22-1123 | smaarakada hatra yavaglu tumba jana idde irtaare, aadre navembarinda marchwarge illi baroke atyanta sookta samayavaadrinda aaga innoo jasti jana irtaare. | The monument is busy most of the time but especially from November to March because that is the best time for visiting it. |  | 0.00 |
| IN22-1124 | eega koviddinda jana barodu swalpa kadme aagide, haagaagi neevu belagge bega bandre aaraamaagi chitrikarana madkobahudu. | The crowds have deteriorated a little due to covid so if you come early morning you should be able to shoot in peace. |  | 0.00 |
| IN22-1143 | ee sthalagala baggeyella naanu eegaagle tumba odideeni, aadre kaledsala aurangaabaadige hogodakke samaya irlilla. | I have already read so much about these places and last time I was out of time to visit Aurangabad. |  | 0.00 |
| IN22-1150 | saamaanya shake ೬೦೦rinda ೧೦೦೦daa madhye nirmanavagiro ellora guhegalalli ೧೦೦ hindoo, jaina mattu bouddha guhegalive, adralli ೩೪ allige bheti kodoru nodoke muktavaagive. | They are constructed between 600 and 1000 CE, the Ellora Caves consist of 100 Hindu, Jain, and Buddhist caves, out of which 34 are open to visitors. |  | 0.00 |
| IN22-1154 | elloraada guhegalalli ೧೬neyadagiro kailasnath devalaya ondu ekashilaa kattada, adanna eeshvaranige anta rashtrakootara aalvikeya kaaldalli nirmislaaytu. | The 16th cave of the Ellora Caves, Kailasanatha is a monolithic structure built during the Rashtrakuta Dynasty and dedicated to Lord Shiva. |  | 0.00 |
| IN22-1162 | ee musalmana shraddhaakendradalli ottu ೫೦ bahubhujada kambagalu, ettarada stambhagopuragalu, mattu ashcharya huttisuvantha kamanugalu kanasigatve. | This Islamic shrine features a total of 50 polygonal pillars, towering minarets, and awe-inspiring arches. |  | 0.00 |
| IN22-1164 | haam, janapriyavaada ellora guhegalalli saamaanya shakeya ೯neey shatamaanadalli utkhananavadantha aidu praachina jaina guhalayagala samucchaya ide, adu aurangaabaadina atyanta kutuhalakari smaarakagalalli ondaagide. | Yes, Excavated back in the 9th century CE, a conglomeration of five ancient Jain caves lie at the popular Ellora Caves and make for one of the most interesting Aurangabad monuments. |  | 0.00 |
| IN22-1222 | sariyagi helde. pouratva kayde jaati, matah, linga ityaadigala bheda ilde ella prajegalgoo matah chalaiso avakasha niidatte. | Exactly. The Citizenship Act allows all citizens to vote regardless of any discrimination based on caste, religion, gender etc. |  | 0.00 |
| IN22-1266 | illandre neevu nimma ration cardina prati athawa naaneega nimge kodo arjiyalli patti madiro bere ondashtu daakhalegalalli yaavudannaadru kodbahudu. | You can also go for a copy of your ration card, and a few other documents that are listed on a form I'll give you. |  | 0.00 |
| KANG-ALAR-155892 | hodike | (hist.) a kind of tax. | Hey | 0.00 |
| KANG-TEST-00076 | bandru avru | They came | I know | 0.00 |
| KANG-ALAR-083499 | dvi khura | the split hoof.; a horse, that has split hooves. | I know | 0.61 |
| KANG-ALAR-088236 | nibidalle | the tree Memecylon umbellatum (= M. edule) of Melastomataceae family. | I know | 0.82 |
| KANG-ALAR-155647 | hogute | the act or fact of entering into or coming into. | Hey | 1.05 |
| KANG-ALAR-087749 | nigama | the veda or vedic text.; the words or passage quoted from the vedas. | no | 1.11 |
| KANG-ALAR-060576 | ghat | a sweet smell; pleasant odour; fragrance. | hey | 1.13 |
| KANG-ALAR-111694 | bennudabbe | the upper or outer side of a split bamboo or rattan. | I know | 1.16 |

**Remaining gated work**

| Stage | Status |
|---|---|
| Gate A | Kannada review and explicit user confirmation pending; resolve any verification errors first. |
| Phase B | LoRA training and local/Colab/Kaggle training scripts not completed. No trained-model measurements. |
| Gate B | Compare the approved-data student with this frozen baseline. Diagnose instead of extending training if benchmark and negative controls do not improve. |
| Phase C | Merge and Q8_0/Q5_K_M/Q4_K_M conversion, accuracy/size/load measurements, S23 FE recommendation and stale Settings label fix pending. |

No new accuracy gain, quantization-loss result or device recommendation can be claimed before those stages run.
