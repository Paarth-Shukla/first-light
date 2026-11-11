"""pipeline.papers text handling: LaTeX cleanup, sentence splitting and the extractive digest.

The digest cases run on eight real arXiv abstracts saved in tests/fixtures/papers/arxiv-idlist.xml.
"""

import unittest
from pathlib import Path

from pipeline import papers

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "papers"


def idlist_entries():
    return {entry["id"]: entry for entry in papers.parse_arxiv((FIXTURES / "arxiv-idlist.xml").read_bytes())["entries"]}


class CleanLatexTest(unittest.TestCase):
    def test_symbols_scripts_and_fonts(self):
        cases = [
            (r"a 3.2$\times$ speedup", "a 3.2× speedup"),
            (r"$O(n^2)$ time", "O(n²) time"),
            (r"MoS$_2$ transistors", "MoS₂ transistors"),
            (r"at 300$^\circ$C", "at 300°C"),
            (r"$\alpha=0.5$ and $\pi_0$", "α=0.5 and π₀"),
            (r"$\mathcal{O}(\sqrt{n})$", "O(√n)"),
            (r"\textbf{Fast}SAM", "FastSAM"),
            (r"$\frac{1}{2}$ of $10^{-3}$", "1/2 of 10⁻³"),
            (r"$T_{\text{max}}$", "T_max"),
            (r"$x^\alpha$", "x^α"),
            (r"world models$\unicode{x2014}$learned simulators", "world models—learned simulators"),
            (r"TB$\wedge$Synth", "TB∧Synth"),
            (r"$5.9\times10^{10}$ times", "5.9×10¹⁰ times"),
            (r"9 $\mu$s", "9 μs"),
            (r"Schr\"odinger and {\'e}t\'e", "Schrödinger and été"),
            (r"``quoted''", "“quoted”"),
            (r"see Fig.~3 and \cite{smith2020}", "see Fig. 3 and"),
            (r"\href{https://x.org}{our site}", "our site"),
            (r"50\% of \$ costs", "50% of $ costs"),
            (r"$\sim$3x faster", "~3x faster"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(papers.clean_latex(raw), expected)

    def test_prices_and_urls_are_left_alone(self):
        self.assertEqual(papers.clean_latex("costs $5 and $10 per hour"), "costs $5 and $10 per hour")
        self.assertEqual(papers.clean_latex("see https://x.org/~user/a"), "see https://x.org/~user/a")

    def test_whitespace_collapses_and_empty_is_empty(self):
        self.assertEqual(papers.clean_latex("two\n  lines\t here"), "two lines here")
        self.assertEqual(papers.clean_latex(""), "")
        self.assertEqual(papers.clean_latex(None), "")

    def test_real_abstracts_have_no_latex_debris(self):
        for entry in idlist_entries().values():
            for text in (entry["title"], entry["abstract"]):
                with self.subTest(id=entry["id"]):
                    for debris in ("$", "\\", "{", "}"):
                        self.assertNotIn(debris, text)
        wmpa = idlist_entries()["2611.10316"]["abstract"]
        self.assertIn("world models—learned simulators", wmpa)
        self.assertIn("5.9×10¹⁰", wmpa)


class SplitSentencesTest(unittest.TestCase):
    CASES = [
        ("plain", "We build a chip. It is fast.", ["We build a chip.", "It is fast."]),
        ("e.g.", "Accelerators, e.g. TPUs, help. We test.", ["Accelerators, e.g. TPUs, help.", "We test."]),
        ("i.e.", "One mode, i.e. Turbo, wins. We test.", ["One mode, i.e. Turbo, wins.", "We test."]),
        ("et al. year", "Smith et al. (2023) showed it. We extend it.", ["Smith et al. (2023) showed it.", "We extend it."]),
        ("et al. name", "As in Smith et al. Jones disagreed.", ["As in Smith et al. Jones disagreed."]),
        ("decimal", "It runs at 3.5 GHz. Power is low.", ["It runs at 3.5 GHz.", "Power is low."]),
        ("Fig.", "As Fig. 3 shows, it works. Done.", ["As Fig. 3 shows, it works.", "Done."]),
        ("Figs.", "See Figs. 2 and 3. Next we test.", ["See Figs. 2 and 3.", "Next we test."]),
        ("Eq.", "By Eq. 5 the loss falls. We stop.", ["By Eq. 5 the loss falls.", "We stop."]),
        ("vs.", "RVV vs. CGRA is compared. We find gains.", ["RVV vs. CGRA is compared.", "We find gains."]),
        ("approx.", "It uses approx. 40% less power. Good.", ["It uses approx. 40% less power.", "Good."]),
        ("percent end", "Latency drops by 12%. We also cut cost.", ["Latency drops by 12%.", "We also cut cost."]),
        ("ratio end", "It is 3.2x faster than ours. Our code is open.", ["It is 3.2x faster than ours.", "Our code is open."]),
        ("lone capital", "It beats model B. The rest lose.", ["It beats model B. The rest lose."]),
        ("question", "Can LLMs design chips? We show they can.", ["Can LLMs design chips?", "We show they can."]),
        ("exclamation", "It works! We are pleased.", ["It works!", "We are pleased."]),
        ("closing paren", "It is fast (see Fig. 2). We explain why.", ["It is fast (see Fig. 2).", "We explain why."]),
        ("closing quote", 'We call it "Foo." The name stuck.', ['We call it "Foo."', "The name stuck."]),
        ("lowercase next", "It takes 5 min. the rest is idle.", ["It takes 5 min. the rest is idle."]),
        ("camel-case name", "We beat the baselines. mHC achieves more.", ["We beat the baselines.", "mHC achieves more."]),
        ("initials", "Built by J. R. Smith at MIT. It ships.", ["Built by J. R. Smith at MIT.", "It ships."]),
        ("unit after number", "The core draws 3 W. The rest sleeps.", ["The core draws 3 W.", "The rest sleeps."]),
        ("dotted abbreviation", "Funded by the U.S. Army and others. Done.", ["Funded by the U.S. Army and others.", "Done."]),
        ("url end", "Code is at https://github.com/x/y. We welcome use.", ["Code is at https://github.com/x/y.", "We welcome use."]),
        ("arXiv id", "This extends arXiv:2611.01234. Code follows.", ["This extends arXiv:2611.01234.", "Code follows."]),
        ("enumeration", "Our contributions: 1. We propose PIM. 2. We test it.", ["Our contributions: 1. We propose PIM.", "2. We test it."]),
        ("section number", "Details are in Section 3. We conclude.", ["Details are in Section 3.", "We conclude."]),
        ("ellipsis", "The question remains open... We try.", ["The question remains open...", "We try."]),
        ("unicode ellipsis", "It remains open… We try.", ["It remains open…", "We try."]),
        ("company abbreviation", "Built at Nvidia Corp. The design is new.", ["Built at Nvidia Corp. The design is new."]),
        ("cf.", "Results differ, cf. Table 2. We discuss.", ["Results differ, cf. Table 2.", "We discuss."]),
        ("etc. ends", "Use CPUs, GPUs, etc. We compare them.", ["Use CPUs, GPUs, etc.", "We compare them."]),
        ("Ph.D.", "Two Ph.D. Students helped. Thanks.", ["Two Ph.D. Students helped.", "Thanks."]),
        ("No.", "See Patent No. 5 for it. Done.", ["See Patent No. 5 for it.", "Done."]),
        ("no final stop", "We build it. It works", ["We build it.", "It works"]),
        ("newlines", "We build\n it.\n\nIt   works.", ["We build it.", "It works."]),
        ("digit start", "Power drops. 3D stacking helps.", ["Power drops.", "3D stacking helps."]),
        ("parenthesis start", "We test it. (Results vary.)", ["We test it. (Results vary.)"]),
        ("list markers", "It has two properties. (i) It is fast. (ii) It is small.",
         ["It has two properties.", "(i) It is fast.", "(ii) It is small."]),
        ("empty", "", []),
    ]

    def test_tricky_cases(self):
        self.assertGreaterEqual(len(self.CASES), 25)
        for name, text, expected in self.CASES:
            with self.subTest(name):
                self.assertEqual(papers.split_sentences(text), expected)

    def test_real_abstracts_split_into_whole_sentences(self):
        for entry in idlist_entries().values():
            sentences = papers.split_sentences(entry["abstract"])
            with self.subTest(id=entry["id"]):
                self.assertEqual(" ".join(sentences), entry["abstract"])
                self.assertGreaterEqual(len(sentences), 4)
                for sentence in sentences:
                    self.assertRegex(sentence, r"^[A-Z0-9\"(]")
                    self.assertLess(len(sentence), 600)
                    self.assertRegex(sentence, r"[.!?)\"]$")


class DigestTest(unittest.TestCase):
    """Digests of eight real abstracts: every field verbatim, the right sentence in each slot."""

    EXPECTED = {
        "2611.07149": {  # FastAFD
            "method": "We build and tune FastAFD, an AFD engine for GB200 NVL72",
            "result": "Experiments show that AFD has a throughput advantage of up to 1.17x",
            "problem": "Whether this advantage holds on rack-scale NVLink systems",
        },
        "2611.07496": {  # ZYFA
            "method": "We present ZYFA, prefill kernels for the MI355X",
            "result": "ZYFA achieves 1.16-1.76x the throughput of AITER",
        },
        "2611.09254": {  # TwinHash
            "method": "We present TwinHash, a unified object management architecture",
            "result": "TwinHash reduces end-to-end wall-clock time by up to 87%",
        },
        "2611.08543": {  # SAFTAC
            "problem": "Circuit design for analog integrated circuits (ICs) is challenging",
            "method": "Using this dataset, we present SAFTAC",
            "result": "showing improvements over the strongest closed-source LLM by 15.9% and 7.8%",
        },
        "2611.06910": {  # FrontierPhysics
            "problem": "However, existing physics benchmarks only evaluate fixed questions",
            "method": "We introduce FrontierPhysics, an end-to-end benchmark with 56 tasks",
            "result": "no configuration passes more than 46 of its 168 rollouts",
        },
        "2611.08373": {  # SLA: the abstract reports no numbers, so there is no result line
            "method": "We present SLA, a Spatial-Language-Action Model",
            "result": "",
        },
        "2611.13931": {  # TAPCO-G: no "we" anywhere; the sentence opening with the name is the method
            "problem": "Post-placement timing and power co-optimization is critical",
            "method": "TAPCO-G combines LLM-guided optimizer adaptation",
            "result": "with a mean quality score gain of 5.516 points",
        },
        "2611.10316": {  # WMPA: the problem is the uncharacterised energy, the result follows the method
            "problem": "have not been characterized",
            "method": "we propose the World Model Planning Accelerator (WMPA)",
            "result": "With a design target of 40x lower power",
        },
    }

    def test_fields_are_verbatim_sentences(self):
        entries = idlist_entries()
        self.assertEqual(set(entries), set(self.EXPECTED))
        for pid, entry in entries.items():
            result = papers.digest(entry["abstract"], entry["title"])
            sentences = papers.split_sentences(entry["abstract"])
            with self.subTest(id=pid):
                self.assertEqual(set(result), {"gist", "problem", "method", "result"})
                for field, text in result.items():
                    if text:
                        self.assertIn(text, sentences, field)
                self.assertTrue(result["gist"])
                self.assertLessEqual(len(result["gist"]), papers.GIST_MAX)
                used = [result[field] for field in ("problem", "method", "result") if result[field]]
                self.assertEqual(len(used), len(set(used)), "problem/method/result repeat a sentence")

    def test_expected_sentences(self):
        entries = idlist_entries()
        for pid, expected in self.EXPECTED.items():
            result = papers.digest(entries[pid]["abstract"], entries[pid]["title"])
            for field, fragment in expected.items():
                with self.subTest(id=pid, field=field):
                    if fragment:
                        self.assertIn(fragment, result[field])
                    else:
                        self.assertEqual(result[field], "")

    def test_gist_prefers_a_standalone_sentence_naming_the_work(self):
        entries = idlist_entries()
        gist = papers.digest(entries["2611.07149"]["abstract"], entries["2611.07149"]["title"])["gist"]
        self.assertTrue(gist.startswith("We build and tune FastAFD"), gist)

    def test_gist_names_the_work_not_its_setting(self):
        entries = idlist_entries()
        gist = papers.digest(entries["2611.07496"]["abstract"], entries["2611.07496"]["title"])["gist"]
        self.assertIn("ZYFA achieves 1.16-1.76x", gist, "FP8 in the title is the setting; ZYFA is the work")

    def test_hedges_are_not_methods_or_gists(self):
        abstract = ("Tactile sensing varies widely across sensors. We present LingBot-Touch, a tactile model "
                    "for many sensors. We believe the findings in this work demonstrate the potential of "
                    "shared tactile data for robots.")
        result = papers.digest(abstract, "Learning Heterogeneous Tactile Representation")
        self.assertTrue(result["method"].startswith("We present LingBot-Touch"))
        self.assertFalse(result["gist"].startswith("We believe"))

    def test_title_names(self):
        self.assertEqual(papers.title_names("ZYFA: Speed and Accuracy of FP8 FlashAttention on AMD CDNA4"),
                         {"ZYFA": 1.0, "FP8": 0.5, "FlashAttention": 0.5, "AMD": 0.5, "CDNA4": 0.5})
        self.assertEqual(papers.title_names("The World Model Planning Accelerator (WMPA): Hardware"), {"WMPA": 0.5})
        self.assertEqual(papers.title_names("Short plain title"), {})

    def test_degenerate_abstracts(self):
        self.assertEqual(papers.digest(""), {"gist": "", "problem": "", "method": "", "result": ""})
        long_sentence = "We propose " + "a very long clause, " * 20 + "and stop."
        result = papers.digest(long_sentence)
        self.assertEqual(result["method"], long_sentence)
        self.assertEqual(result["gist"], "", "a sentence over GIST_MAX is never cut to fit")


if __name__ == "__main__":
    unittest.main()
