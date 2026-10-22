"""Safety boundaries for the gated student experiment; no invented translations."""
from difflib import SequenceMatcher
import random
import unittest
from scripts.student_pipeline.contract import assert_prompt_contract, exact, within_one_edit, select_hints, prompt, SYSTEM, glossary, glossary_matches
from scripts.student_pipeline.checks import FuzzyIndex, compact, family_key, chrf_score, chrf_stats, row_issues
from scripts.student_pipeline.data import spelling_variants
from scripts.probe_student_quality import edit_distance, glossary_matches as original_matches

class StudentGateTests(unittest.TestCase):
    def test_prompt_is_current_android_contract(self):
        self.assertTrue(assert_prompt_contract())
        value=prompt('naale', [('thing','meaning')])
        self.assertIn('naale = tomorrow\n',value)
        self.assertTrue(value.startswith('<|im_start|>system\n'+SYSTEM))
        self.assertTrue(value.endswith('<|im_start|>assistant\n'))

    def test_exact_glossary_preserves_punctuation_boundary(self):
        self.assertEqual(exact(' A   B ', [('a b','stored')]),'stored')
        self.assertIsNone(exact('a b?', [('a b','stored')]))

    def test_one_edit_optimization_matches_full_distance(self):
        rng=random.Random(42)
        for _ in range(300):
            a=''.join(rng.choices('abcde',k=rng.randrange(1,12)))
            b=''.join(rng.choices('abcde',k=rng.randrange(1,12)))
            self.assertEqual(within_one_edit(a,b),edit_distance(a,b)<=1)

    def test_glossary_matches_unchanged(self):
        entries=glossary()
        for source,_ in entries[::17]:
            self.assertEqual(glossary_matches(source,entries)[:8],original_matches(source,entries))

    def test_fuzzy_index_does_not_lose_bruteforce_matches(self):
        rng=random.Random(4);texts=[]
        for _ in range(100):texts.append(''.join(rng.choices('abcde ',k=rng.randrange(4,45))))
        index=FuzzyIndex(.88)
        for i,text in enumerate(texts):index.add(text,i)
        for text in texts:
            query=text[:2]+'x'+text[3:]
            found={r['match'] for r in index.matches(query,True)}
            for i,target in enumerate(texts):
                a,b=compact(query),compact(target)
                must=family_key(a)==family_key(b) or SequenceMatcher(None,a,b,autojunk=False).ratio()>=.88
                if 4<=len(a)<=10 and 4<=len(b)<=10 and edit_distance(a,b)<=1:must=True
                if must:self.assertIn(i,found)

    def test_short_typo_is_reserved(self):
        index=FuzzyIndex(.88);index.add('abcdef',1)
        self.assertTrue(index.matches('abcxef'))

    def test_chrF_identity_and_no_overlap(self):
        self.assertAlmostEqual(chrf_score(chrf_stats('abcdef','abcdef')),100)
        self.assertEqual(chrf_score(chrf_stats('abcdef','uvwxyz')),0)

    def test_structural_checks_quarantine_changes(self):
        self.assertIn('number_mismatch',row_issues('item 2','item 3','conversation'))
        self.assertIn('name_mismatch:george',row_issues('bhuvana','george','conversation',['george']))
        self.assertIn('ambiguous_bidi_review',row_issues('bidi','reference placeholder','conversation'))
        self.assertIn('invalid_abstention_target',row_issues('qzxxzv','anything','abstention'))

    def test_variants_preserve_protected_words(self):
        row={'id':'unit','romanized_input':'naale sampleword collegege TestName','original_kannada':'TestName','names':['testname']}
        variants=spelling_variants(row,42)
        self.assertTrue(3<=len(variants)<=5)
        for value,kind in variants:
            self.assertIn('naale',value);self.assertIn('TestName',value)
        self.assertEqual(variants,spelling_variants(row,42))

if __name__=='__main__':unittest.main()
