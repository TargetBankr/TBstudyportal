#!/usr/bin/env python3
"""
Offline tests: no API key or network needed. A fake Gemini injects the failures the real
pipeline has to survive (bad items, duplicates, wrong keys, disputed answers, quota, bad JSON).

Run:  python test_offline.py
"""
import json
import random
import re
import shutil
import string
import sys
import tempfile
from collections import Counter
from pathlib import Path

import generate as g
LETTERS = 'ABCD'
from topics import SUBJECTS, validate_config


class FakeAPIError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def rword(rng, n=12):
    return "".join(rng.choice(string.ascii_lowercase) for _ in range(n))


class FakeGemini(g.Gemini):
    """Deterministic stand-in. The correct option always starts with 'right'."""

    def __init__(self, fail_plan=None, **kw):
        super().__init__("fake", "fake-model", None, rpm=1000)
        self.rng = random.Random(kw.get("seed", 1))
        self.fail_plan = fail_plan or {}  # call_no -> exception or "garbage"
        self.n = 0
        self.slept = 0.0
        self.first_gen = True
        self.gen_calls = 0

    def _sleep(self, s):
        self.slept += s

    def _make_q(self, level, tag=""):
        stem = f"What does {rword(self.rng)} {rword(self.rng)} do in {rword(self.rng)} {tag}?"
        letters = "ABCD"
        ans = self.rng.choice(letters)
        opts = []
        for L in letters:
            opts.append(f"right {rword(self.rng, 6)}" if L == ans else f"wrong {rword(self.rng, 6)}")
        return {"q": stem, "options": opts, "answer": ans, "level": level}

    def _generate(self, prompt, model, temperature, max_out):
        self.n += 1
        plan = self.fail_plan.get(self.n)
        if isinstance(plan, Exception):
            raise plan
        if plan == "garbage":
            return "Sorry, here you go: not json at all"
        if "Write exactly" in prompt:
            return self._gen(prompt)
        payload = re.search(r"(?:Questions|Disputed questions):\n(\[.*\])\n\nReturn ONLY", prompt, re.S)
        rows = json.loads(payload.group(1))
        if "final examiner" in prompt:
            res = []
            for r in rows:
                if "AMBIGUOUS" in r["q"]:
                    res.append({"n": r["n"], "final": "INVALID", "reason": "two answers"})
                else:
                    right = [L for L, t in r["options"].items() if t.startswith("right")][0]
                    res.append({"n": r["n"], "final": right, "reason": "textbook"})
            return json.dumps({"results": res})
        res = []
        for r in rows:
            right = [L for L, t in r["options"].items() if t.startswith("right")][0]
            if "VERIFIERWRONG" in r["q"]:
                answer = "A" if right != "A" else "B"
            else:
                answer = right
            issue = "ambiguous" if "AMBIGUOUS" in r["q"] else None
            res.append({"n": r["n"], "answer": answer, "issue": issue})
        return json.dumps({"results": res})

    def _gen(self, prompt):
        self.gen_calls += 1
        n = int(re.search(r"Write exactly (\d+)", prompt).group(1))
        items = []
        for i in range(n):
            lvl = "easy" if i < n * 0.4 else ("moderate" if i < n * 0.8 else "hard")
            items.append(self._make_q(lvl))
        if self.first_gen and n >= 12:
            self.first_gen = False
            items[1] = dict(items[0])                                   # exact duplicate
            items[2] = {"q": "Only three options here?", "options": ["a", "b", "c"], "answer": "A", "level": "easy"}
            items[3]["options"][0] = "All of the above"                 # forbidden option
            items[4]["q"] += " AMBIGUOUS"                               # verifier flags -> dropped
            wrong = [L for L, t in zip("ABCD", items[5]["options"]) if t.startswith("wrong")][0]
            items[5]["answer"] = wrong                                  # author's key is wrong -> fixed
            items[6]["q"] += " VERIFIERWRONG"                           # checker wrong -> author confirmed
        return json.dumps({"questions": items})


def setup_tmp():
    tmp = Path(tempfile.mkdtemp(prefix="qbank_test_"))
    g.BANK, g.CACHE, g.REVIEW = tmp / "bank", tmp / "cache", tmp / "review"
    return tmp


def run(argv, fake):
    return g.main(argv, gem_factory=lambda a: fake)


def check_file(path, expected):
    text = path.read_text(encoding="utf-8")
    qs, answers = g.parse_md(text)
    assert len(qs) == expected, f"{path.name}: {len(qs)} questions, expected {expected}"
    assert len(answers) == expected, "answer count mismatch"
    assert text.startswith("# MOCK: "), "missing MOCK header"
    assert "\n\n## EN\n" in text and "\n\n## ANSWERS\n" in text, "section layout"
    for (q, opts), a in zip(qs, answers):
        assert len(opts) == 4
        assert opts["ABCD".index(a)].startswith("right"), f"key wrong for: {q}"
    dist = {L: answers.count(L) for L in "ABCD"}
    assert max(dist.values()) - min(dist.values()) <= 1, f"unbalanced answers {dist}"
    # original notebook's regex must also work on our lines
    for line in text.splitlines():
        if re.match(r"\d+\. ", line) and " A) " in line:
            assert re.match(r"\s*\d+\.\s*(.+?)\s*A\)", line)
    return qs, answers


def test_config():
    assert validate_config()
    for no, s in SUBJECTS.items():
        assert sum(m[3] for m in s["mocks"]) == 750
        assert all(25 <= m[3] <= 50 for m in s["mocks"])
    assert sum(len(s["mocks"]) for s in SUBJECTS.values()) == 44
    print("ok  topic map: 2 x 750, 44 mocks, all 25..50")


def test_happy_path_with_faults():
    tmp = setup_tmp()
    fake = FakeGemini()
    assert run(["--shift", "2", "--only", "S2_19"], fake) == 0
    mock = [m for m in SUBJECTS[2]["mocks"] if m[0] == "S2_19"][0]
    f = g.bank_file(2, mock)
    assert f.exists()
    qs, answers = check_file(f, 30)
    assert len({g.norm(q) for q, _ in qs}) == 30, "duplicate stems survived"
    assert not any("AMBIGUOUS" in q for q, _ in qs), "ambiguous question survived"
    assert not any("All of the above" in " ".join(o) for _, o in qs)
    stats = g.load_cache("S2_19")["stats"]
    assert stats.get("key_fixed") == 1, stats
    assert stats.get("dropped_invalid") == 1, stats
    assert stats.get("rejected_format", 0) >= 2, stats
    assert stats.get("key_confirmed_after_dispute", 0) >= 1, stats
    assert fake.gen_calls >= 2, "top-up round did not happen"
    log = [json.loads(l) for l in (g.REVIEW / "review_log.jsonl").read_text().splitlines()]
    assert {e["action"] for e in log} >= {"key_fixed", "dropped", "confirmed"}, log
    # easy -> hard ordering inside the file is by level
    final_levels = stats["levels"]
    assert sum(final_levels.values()) == 30
    print("ok  faults handled: dup/format rejected, key fixed, ambiguous dropped, top-up, review log")
    shutil.rmtree(tmp)


def test_levels_sorted():
    tmp = setup_tmp()
    fake = FakeGemini()
    run(["--shift", "1", "--only", "S1_04"], fake)
    cache = g.load_cache("S1_04")
    raw_order = [q["level"] for q in cache["questions"]]
    assert raw_order, "cache empty"
    items = g.finalize_items(cache["questions"], "S1_04")
    seq = [g.LEVELS[i["level"]] for i in items]
    assert seq == sorted(seq), "not easy->hard"
    print("ok  easy -> moderate -> hard ordering")
    shutil.rmtree(tmp)


def test_quota_then_resume():
    tmp = setup_tmp()
    quota = FakeAPIError(429, "429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    # call 1 = generate, 2+3 = the two verify passes, 4 = arbitration, 5 = top-up generate -> quota
    fake = FakeGemini(fail_plan={5: quota})
    assert run(["--shift", "2", "--only", "S2_19"], fake) == 0
    mock = [m for m in SUBJECTS[2]["mocks"] if m[0] == "S2_19"][0]
    assert not g.bank_file(2, mock).exists(), "incomplete mock must not be finalised"
    cache = g.load_cache("S2_19")
    assert 20 <= len(cache["questions"]) < 30, len(cache["questions"])
    assert all(q["v"] for q in cache["questions"]), "partial progress should be verified"
    assert (g.BANK / "STATUS.md").exists()
    # resume
    fake2 = FakeGemini(seed=2)
    assert run(["--shift", "2", "--only", "S2_19"], fake2) == 0
    check_file(g.bank_file(2, mock), 30)
    assert fake2.gen_calls == 1, f"resume should only top up, made {fake2.gen_calls} generate calls"
    # third run does nothing
    fake3 = FakeGemini()
    run(["--shift", "2", "--only", "S2_19"], fake3)
    assert fake3.n == 0, "finished mock should be skipped with zero API calls"
    print("ok  daily quota stops cleanly, resume tops up only the gap, finished mock skipped")
    shutil.rmtree(tmp)


def test_rate_limit_and_bad_json():
    tmp = setup_tmp()
    rate = FakeAPIError(429, "429 RESOURCE_EXHAUSTED Please retry in 7.5s")
    fake = FakeGemini(fail_plan={1: rate, 2: "garbage", 3: FakeAPIError(503, "503 UNAVAILABLE overloaded")})
    assert run(["--shift", "1", "--only", "S1_12"], fake) == 0
    mock = [m for m in SUBJECTS[1]["mocks"] if m[0] == "S1_12"][0]
    check_file(g.bank_file(1, mock), 25)
    assert fake.slept >= 9.5, f"did not honour retry delay (slept {fake.slept})"
    print("ok  minute-rate limit waits, garbage JSON retried, 503 retried")
    shutil.rmtree(tmp)


def test_persistent_rate_limit_is_quota():
    tmp = setup_tmp()
    rate = FakeAPIError(429, "429 RESOURCE_EXHAUSTED retry in 1s")
    fake = FakeGemini(fail_plan={i: rate for i in range(1, 20)})
    assert run(["--shift", "1", "--only", "S1_12"], fake) == 0
    mock = [m for m in SUBJECTS[1]["mocks"] if m[0] == "S1_12"][0]
    assert not g.bank_file(1, mock).exists()
    print("ok  persistent 429 ends the run cleanly")
    shutil.rmtree(tmp)


def test_fatal_model_error():
    tmp = setup_tmp()
    fake = FakeGemini(fail_plan={1: FakeAPIError(404, "404 NOT_FOUND models/foo is not found")})
    assert run(["--shift", "1", "--only", "S1_12"], fake) == 1
    print("ok  unknown model -> exit code 1")
    shutil.rmtree(tmp)


def test_cross_mock_dedup_and_master():
    tmp = setup_tmp()
    fake = FakeGemini()
    run(["--shift", "1", "--only", "S1_12,S1_13"], fake)
    a = g.parse_md(g.bank_file(1, SUBJECTS[1]["mocks"][11]).read_text())[0]
    b = g.parse_md(g.bank_file(1, SUBJECTS[1]["mocks"][12]).read_text())[0]
    assert not ({g.norm(q) for q, _ in a} & {g.norm(q) for q, _ in b})
    master = (g.BANK / "subject1" / "_MASTER_subject1.md").read_text()
    assert master.count("# MOCK: ") == 2
    seen = g.load_seen()
    dup_q, dup_o = a[0]
    assert seen.is_dup(dup_q, dup_o), "bank question not recognised as duplicate"
    status = (g.BANK / "STATUS.md").read_text()
    assert "S1_12" in status and "Total:" in status
    print("ok  cross-mock dedup, master file, status file")
    shutil.rmtree(tmp)


def test_dedup_does_not_flag_templated_stems():
    seen = g.Seen()
    seen.add("What is the full form of RAM?", ["Random Access Memory", "Read Access Memory", "Run All Memory", "Real Active Memory"], 1)
    assert not seen.is_dup("What is the full form of ROM?", ["Read Only Memory", "Random Only Memory", "Run Once Memory", "Real Only Memory"])
    assert seen.is_dup("What is the full form of RAM?", ["x", "y", "z", "w"])
    print("ok  'full form of RAM' vs 'full form of ROM' are not false duplicates")


def test_clean_item_rules():
    ok = {"q": "Which key refreshes a web page?", "options": ["F1", "F5", "F9", "F12"], "answer": "b", "level": "Easy"}
    c = g.clean_item(ok)
    assert c and c["answer"] == "B" and c["level"] == "easy"
    assert g.clean_item(dict(ok, options=["F1", "F5", "F9"])) is None
    assert g.clean_item(dict(ok, options=["F1", "F1", "F9", "F12"])) is None
    assert g.clean_item(dict(ok, options=["A) F1", "F5", "F9", "F12"]))["options"][0] == "F1"
    assert g.clean_item(dict(ok, options=["F1", "Both A and B", "F9", "F12"])) is None
    assert g.clean_item(dict(ok, options=["F1", "None of the above", "F9", "F12"])) is None
    assert g.clean_item(dict(ok, answer="E")) is None
    assert g.clean_item(dict(ok, q="Pick one B) here which breaks the format?")) is None
    print("ok  validation rules")


def test_numeric_options_shuffled_and_balanced():
    items = [{"q": f"How many bits are in a byte, variant {i}?", "options": ["16", "8", "4", "32"],
              "answer": "B", "level": "easy", "explanation": "x"} for i in range(40)]
    out = g.finalize_items(items, "X")
    dist = Counter(o["answer"] for o in out)
    assert max(dist.values()) - min(dist.values()) <= 1, dist
    assert all(o["options"][LETTERS.index(o["answer"])] == "8" for o in out), "key must follow the option"
    print("ok  numeric options shuffled, answer key balanced")


def test_length_bias_filter():
    ok = {"q": "Which key refreshes a web page?", "options": ["Alt", "Control", "Shift", "The function key numbered five"], "answer": "D"}
    assert g.length_biased(g.clean_item(ok))
    fine = {"q": "Which key refreshes a web page?", "options": ["Function key five", "Function key one", "Function key nine", "Function key two"], "answer": "A"}
    assert not g.length_biased(g.clean_item(fine))
    print("ok  clearly-longest correct option is rejected")


def test_near_duplicate_wording():
    seen = g.Seen()
    seen.add("Which attribute sets the width of an image in pixels on a page?", ["width", "size", "w", "px"], 2)
    assert seen.is_dup("Which attribute sets the width of an image in pixels on the page?", ["width", "len", "wide", "px"])
    assert not seen.is_dup("Which attribute gives alternate text for an image on a page?", ["alt", "title", "src", "name"])
    print("ok  reworded duplicate caught, different fact kept")


def test_explanations_written_and_parse_ignores_them():
    tmp = setup_tmp()
    items = [{"q": "What does the F5 key do in a browser?", "options": ["Refresh", "Close", "Print", "Save"],
              "answer": "A", "level": "easy", "explanation": "F5 reloads the page."}]
    text = g.render_md("S", "T", g.finalize_items(items, "m"))
    assert "## EXPLANATIONS\n1. F5 reloads the page." in text
    qs, ans = g.parse_md(text)
    assert len(qs) == 1 and len(ans) == 1
    shutil.rmtree(tmp)
    print("ok  explanations section written; answer parsing unaffected")


def test_force_regenerates():
    tmp = setup_tmp()
    fake = FakeGemini()
    run(["--shift", "1", "--only", "S1_13"], fake)
    mock = SUBJECTS[1]["mocks"][12]
    first = g.bank_file(1, mock).read_text()
    fake2 = FakeGemini(seed=9)
    run(["--shift", "1", "--only", "S1_13", "--force"], fake2)
    assert fake2.n > 0 and g.bank_file(1, mock).read_text() != first
    print("ok  --force discards a finished mock and rebuilds it")
    shutil.rmtree(tmp)


def test_sdk_call_path():
    """The real _generate() code path, against a stub client (no network)."""
    seen_kwargs = {}

    class Resp:
        text = '```json\n{"questions": []}\n```'

    class Models:
        def generate_content(self, model, contents, config):
            seen_kwargs.update(model=model, contents=contents, config=config)
            return Resp()

    class Client:
        models = Models()

    gem = g.Gemini("k", "gemini-2.5-flash", None, rpm=1000)
    gem._client = Client()
    out = gem.ask_json("hello", temperature=0.3, max_out=123)
    assert out == {"questions": []}
    cfg = seen_kwargs["config"]
    assert cfg.response_mime_type == "application/json" and cfg.max_output_tokens == 123
    assert seen_kwargs["model"] == "gemini-2.5-flash"
    print("ok  SDK call path builds a valid config and parses fenced JSON")


def test_error_classification_real_shapes():
    day = Exception("429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'status': 'RESOURCE_EXHAUSTED', 'details': "
                    "[{'violations': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}]}}")
    day.code = 429
    minute = Exception("429 RESOURCE_EXHAUSTED. {'error': {'details': [{'violations': "
                       "[{'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier'}]}, {'retryDelay': '34s'}]}}")
    minute.code = 429
    assert g.classify(day) == "quota_day"
    assert g.classify(minute) == "rate"
    assert abs(g.retry_delay(minute, 99) - 36) < 0.01
    nf = Exception("404 NOT_FOUND. models/gemini-x is not found for API version v1beta")
    nf.code = 404
    assert g.classify(nf) == "notfound"
    bad = Exception("400 INVALID_ARGUMENT. API key not valid. Please pass a valid API key.")
    bad.code = 400
    assert g.classify(bad) == "auth"
    print("ok  realistic Google error strings classified correctly")


def test_stubborn_bad_json_skips_mock_not_run():
    tmp = setup_tmp()
    fake = FakeGemini(fail_plan={1: "garbage", 2: "garbage", 3: "garbage"})
    assert run(["--shift", "1", "--only", "S1_12,S1_13"], fake) == 0
    m12 = SUBJECTS[1]["mocks"][11]
    m13 = SUBJECTS[1]["mocks"][12]
    assert not g.bank_file(1, m12).exists()
    assert g.bank_file(1, m13).exists(), "next mock should still run"
    print("ok  3 bad responses in a row skips that mock and continues")
    shutil.rmtree(tmp)


def test_dry_run_and_check():
    tmp = setup_tmp()
    assert g.main(["--check"]) == 0
    assert g.main(["--shift", "2", "--dry-run"]) == 0
    assert g.main([]) == 1
    assert not (g.BANK).exists()
    print("ok  --check, --dry-run (no files), missing --shift")
    shutil.rmtree(tmp)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\nall {len(tests)} tests passed")
