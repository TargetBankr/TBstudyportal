#!/usr/bin/env python3
"""
HARTRON DEO question bank generator (GitHub Actions / local).

Pipeline per mock:
  generate (JSON) -> validate -> dedup -> verify answer key (2nd pass + arbitration)
  -> top up any gaps -> sort easy->hard -> shuffle options -> write markdown.

Output format (same as the Junior Programmer bank):

    # MOCK: Subject - Title

    ## EN
    1. Question? A) opt B) opt C) opt D) opt

    ## ANSWERS
    1. B

Resume-safe: finished mocks are skipped, partial progress is cached in cache/.
"""
import argparse
import difflib
import json
import os
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

from topics import SUBJECTS, validate_config

ROOT = Path(__file__).resolve().parent
BANK = ROOT / "bank"
CACHE = ROOT / "cache"
REVIEW = ROOT / "review"

DEFAULT_MODEL = os.environ.get("QBANK_MODEL", "gemini-3.5-flash-lite")
LEVELS = {"easy": 0, "moderate": 1, "hard": 2}
LETTERS = "ABCD"
MAX_ROUNDS = 5


# --------------------------------------------------------------------------
# Prompts (placeholders use <<NAME>> to avoid clashing with JSON braces)
# --------------------------------------------------------------------------
GEN_PROMPT = """You are writing multiple-choice questions for a Haryana government exam question bank: the HARTRON DEO (Data Entry Operator) written test, computer subjects.

Subject: <<SUBJECT>>
Mock set: <<TITLE>>
Areas to cover: <<FOCUS>>

Write exactly <<N>> NEW multiple-choice questions.

Difficulty progression. Tag every question with "level":
- first ~40%: "easy" (direct recall, definitions, full forms, what-does-this-tool-do)
- next ~40%: "moderate" (comparison, application, shortcut or option purpose, small calculations, output of a formula)
- last ~20%: "hard" (unusual angle, long or tricky wording, "which is NOT", close distractors). Hard means tricky wording or a less common standard fact. It does not mean advanced engineering.

Rules:
1. Level: Indian state-government DEO / clerical computer exam. Facts must be standard, textbook-correct and unambiguous. If you are not sure of a fact, do not use it.
2. Exactly 4 options and exactly ONE correct option. The other three must be clearly wrong. Never use "All of the above", "None of the above", "Both A and B" or any option that refers to other options by letter.
3. Spread the questions across the listed areas. No two questions may test the same fact.
4. Plain text only: no markdown, no newlines inside a question or option. HTML tags may be written as plain text, for example <p>.
5. Do not put "A)", "B)" labels in the options.
6. Correct answers should be spread naturally across positions.
7. English only.

Do not repeat these already-used questions or test the same fact again:
<<PREVIOUS>>

Return ONLY JSON in this shape:
{"questions":[{"q":"question text","options":["opt1","opt2","opt3","opt4"],"answer":"B","level":"easy"}]}
"""

VERIFY_PROMPT = """You are a strict senior examiner checking the answer key of an MCQ bank for the HARTRON DEO computer exam (Windows, networking, computer fundamentals, internet, HTML/DHTML, MS Office).

Solve each question independently from standard textbook knowledge. You are NOT shown the author's key.

For each question return:
- "answer": the single correct option letter (A, B, C or D)
- "issue": null if the question is clean, otherwise one of "ambiguous", "no_correct_option", "multiple_correct", "factual_doubt", "bad_wording". Be strict: if two options are defensibly correct, use "multiple_correct".

Questions:
<<QUESTIONS>>

Return ONLY JSON: {"results":[{"n":1,"answer":"B","issue":null}]}
"""

ARBITRATE_PROMPT = """You are the final examiner for an MCQ bank (HARTRON DEO computer exam). Each question below was disputed: the author's key and an independent checker's answer differ, or the checker flagged a problem.

Decide independently using standard textbook facts (Windows, networking, computer fundamentals, HTML, MS Office). Think carefully about each one.

- "final": the letter of the one correct option if exactly one option is correct, or "INVALID" if none or more than one option is defensible, or the wording is flawed.
- "reason": one short sentence.

Disputed questions:
<<QUESTIONS>>

Return ONLY JSON: {"results":[{"n":1,"final":"B","reason":"..."}]}
"""


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------
class QuotaExhausted(Exception):
    """Daily (or persistent) API quota is gone. Stop cleanly; re-run later."""


class FatalAPIError(Exception):
    """Bad key, unknown model, etc. Re-running will not help until fixed."""


def classify(e):
    code = getattr(e, "code", None)
    low = str(e).lower()
    squashed = low.replace("_", "").replace(" ", "")
    if code == 429 or "resourceexhausted" in squashed or "resource_exhausted" in low:
        if "perday" in squashed or "daily" in low:
            return "quota_day"
        return "rate"
    if code in (500, 502, 503, 504) or "unavailable" in low or "overloaded" in low or "deadline" in low:
        return "server"
    if code == 404 or "not_found" in low or "is not found" in low:
        return "notfound"
    if code in (400, 401, 403) and ("api key" in low or "api_key" in low or "permission" in low):
        return "auth"
    return "other"


def retry_delay(e, default):
    m = re.search(r"retry\w*\W+(?:in\s+)?(\d+(?:\.\d+)?)\s*s", str(e), re.I)
    if m:
        return min(float(m.group(1)) + 2, 120)
    return default


# --------------------------------------------------------------------------
# Gemini wrapper (pacing, retries, JSON parsing)
# --------------------------------------------------------------------------
class Gemini:
    def __init__(self, api_key, model, verify_model=None, rpm=5):
        self.api_key = api_key
        self.model = model
        self.verify_model = verify_model or model
        self.min_gap = 60.0 / max(rpm, 1)
        self._last = 0.0
        self._client = None
        self.calls = 0

    # hooks overridden in offline tests -----------------------------------
    def _sleep(self, s):
        time.sleep(s)

    def _generate(self, prompt, model, temperature, max_out):
        from google import genai
        from google.genai import types
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        resp = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                max_output_tokens=max_out,
            ),
        )
        if not resp.text:
            raise ValueError("empty response (blocked or truncated)")
        return resp.text

    # ---------------------------------------------------------------------
    def _pace(self):
        gap = time.monotonic() - self._last
        if gap < self.min_gap:
            self._sleep(self.min_gap - gap)
        self._last = time.monotonic()

    @staticmethod
    def parse_json(text):
        t = text.strip()
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            pass
        starts = [i for i in (t.find("{"), t.find("[")) if i != -1]
        if not starts:
            raise ValueError("no JSON found")
        s = min(starts)
        e = max(t.rfind("}"), t.rfind("]"))
        return json.loads(t[s:e + 1])

    def ask_json(self, prompt, model=None, temperature=0.7, max_out=32000, attempts=6):
        model = model or self.model
        rate_hits = 0
        parse_fails = 0
        last_err = None
        for attempt in range(1, attempts + 1):
            self._pace()
            self.calls += 1
            try:
                text = self._generate(prompt, model, temperature, max_out)
                return self.parse_json(text)
            except (ValueError, json.JSONDecodeError) as e:
                last_err = e
                parse_fails += 1
                print(f"    bad output ({e}); retry {attempt}/{attempts}", flush=True)
                if parse_fails >= 3:  # don't burn free-tier calls on a stubborn bad response
                    break
                self._sleep(3)
            except Exception as e:  # SDK errors
                kind = classify(e)
                last_err = e
                if kind == "quota_day":
                    raise QuotaExhausted(str(e)[:300])
                if kind == "rate":
                    rate_hits += 1
                    if rate_hits >= 4:
                        raise QuotaExhausted("rate limit kept firing: " + str(e)[:300])
                    d = retry_delay(e, 30 * rate_hits)
                    print(f"    rate limited, waiting {d:.0f}s", flush=True)
                    self._sleep(d)
                elif kind == "server":
                    d = 10 * attempt
                    print(f"    server busy, waiting {d}s", flush=True)
                    self._sleep(d)
                elif kind in ("notfound", "auth"):
                    raise FatalAPIError(f"{kind}: {str(e)[:300]}")
                else:
                    print(f"    API error: {str(e)[:200]}; retry {attempt}/{attempts}", flush=True)
                    self._sleep(5)
        raise RuntimeError(f"gave up after {attempts} attempts: {str(last_err)[:200]}")


# --------------------------------------------------------------------------
# Question cleaning, dedup, rendering
# --------------------------------------------------------------------------
def collapse(s):
    return re.sub(r"\s+", " ", str(s)).strip()


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


LABEL_RE = re.compile(r"(?:^|\s)[A-D]\)\s")
REF_RE = re.compile(
    r"\b(?:both|options?)\s+\(?[A-D]\b|\b(?:all|none)\s+of\s+the\s+above\b|\ball\s+of\s+these\b",
    re.I,
)
PREFIX_RE = re.compile(r"^\(?[A-Da-d][\).]\s+")


def clean_item(it):
    """Return a normalised question dict or None if it breaks a rule."""
    if not isinstance(it, dict):
        return None
    q = collapse(it.get("q", ""))
    opts = it.get("options")
    ans = str(it.get("answer", "")).strip().upper()[:1]
    if len(q) < 10 or not isinstance(opts, list) or len(opts) != 4 or ans not in LETTERS:
        return None
    opts = [PREFIX_RE.sub("", collapse(o)) for o in opts]
    if any(not o for o in opts):
        return None
    if len({norm(o) or o for o in opts}) != 4:
        return None
    for text in [q] + opts:
        if LABEL_RE.search(text) or REF_RE.search(text):
            return None
    level = str(it.get("level", "moderate")).strip().lower()
    if level not in LEVELS:
        level = "moderate"
    return {"q": q, "options": opts, "answer": ans, "level": level, "v": bool(it.get("v", False))}


class Seen:
    """Cross-mock duplicate detector (same stem AND overlapping options, or identical stem)."""

    def __init__(self):
        self.rows = []  # (norm_q, set(norm options), raw_q, subject_no)

    def add(self, q, options, subj):
        self.rows.append((norm(q), {norm(o) for o in options}, q, subj))

    def is_dup(self, q, options):
        nq = norm(q)
        nopts = {norm(o) for o in options}
        for rq, ropts, _, _ in self.rows:
            if nq == rq:
                return True
            if abs(len(nq) - len(rq)) > 0.3 * max(len(nq), len(rq)):
                continue
            sm = difflib.SequenceMatcher(None, nq, rq)
            if sm.real_quick_ratio() < 0.85 or sm.quick_ratio() < 0.85:
                continue
            ratio = sm.ratio()
            if ratio >= 0.97 or (ratio >= 0.85 and len(nopts & ropts) >= 2):
                return True
        return False

    def stems(self, subj, limit=250):
        out = [r[2][:110] for r in self.rows if r[3] == subj]
        return out[-limit:]


MD_Q_RE = re.compile(r"^\s*\d+\.\s*(.*?)\s+A\)\s*(.*?)\s+B\)\s*(.*?)\s+C\)\s*(.*?)\s+D\)\s*(.*)$")


def parse_md(text):
    """-> (list of (q, [o1..o4]), list of answer letters)"""
    qs, answers, section = [], [], None
    for line in text.splitlines():
        if line.startswith("## EN"):
            section = "en"
        elif line.startswith("## ANSWERS"):
            section = "ans"
        elif section == "en":
            m = MD_Q_RE.match(line)
            if m:
                qs.append((m.group(1).strip(), [g.strip() for g in m.groups()[1:]]))
        elif section == "ans":
            m = re.match(r"^\s*\d+\.\s*([A-D])\s*$", line)
            if m:
                answers.append(m.group(1))
    return qs, answers


def render_md(subject_name, title, items):
    lines = [f"# MOCK: {subject_name} - {title}", "", "## EN"]
    for i, it in enumerate(items, 1):
        o = it["options"]
        lines.append(f"{i}. {it['q']} A) {o[0]} B) {o[1]} C) {o[2]} D) {o[3]}")
    lines += ["", "## ANSWERS"]
    lines += [f"{i}. {it['answer']}" for i, it in enumerate(items, 1)]
    return "\n".join(lines) + "\n"


NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def finalize_items(items, mock_id):
    """Sort easy->hard (stable), then shuffle option order to balance the answer key."""
    items = sorted(items, key=lambda it: LEVELS[it["level"]])
    rng = random.Random(mock_id)
    # Balanced answer key: A/B/C/D each get n/4 (+-1) correct answers, in random order.
    targets = (list(LETTERS) * ((len(items) + 3) // 4))[:len(items)]
    rng.shuffle(targets)
    out = []
    for it, target in zip(items, targets):
        correct = it["options"][LETTERS.index(it["answer"])]
        if all(NUM_RE.match(o) for o in it["options"]):
            opts = sorted(it["options"], key=float)  # keep numbers in natural order
        else:
            others = [o for o in it["options"] if o != correct]
            rng.shuffle(others)
            pos = LETTERS.index(target)
            opts = others[:pos] + [correct] + others[pos:]
        out.append({"q": it["q"], "options": opts, "answer": LETTERS[opts.index(correct)], "level": it["level"]})
    return out


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------
def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:80]


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def bank_file(subject_no, mock):
    mid, title = mock[0], mock[1]
    return BANK / SUBJECTS[subject_no]["slug"] / f"{mid}_{slugify(title)}.md"


def is_done(subject_no, mock):
    return bank_file(subject_no, mock).exists()


def load_cache(mid):
    p = CACHE / f"{mid}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"questions": [], "stats": {}}


def save_cache(mid, data):
    atomic_write(CACHE / f"{mid}.json", json.dumps(data, ensure_ascii=False, indent=1))


def load_seen():
    seen = Counter()
    s = Seen()
    for no, subj in SUBJECTS.items():
        for mock in subj["mocks"]:
            f = bank_file(no, mock)
            if f.exists():
                qs, _ = parse_md(f.read_text(encoding="utf-8"))
                for q, opts in qs:
                    s.add(q, opts, no)
    return s


def log_review(entry):
    REVIEW.mkdir(parents=True, exist_ok=True)
    with open(REVIEW / "review_log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def bump(stats, key, n=1):
    stats[key] = stats.get(key, 0) + n


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------
def fmt_for_check(items, extra=None):
    payload = []
    for i, it in enumerate(items, 1):
        row = {"n": i, "q": it["q"], "options": dict(zip(LETTERS, it["options"]))}
        if extra:
            row.update(extra[i - 1])
        payload.append(row)
    return json.dumps(payload, ensure_ascii=False)


def to_letter(x):
    x = str(x or "").strip().upper()[:1]
    return x if x in LETTERS else None


def verify_items(gem, mid, items, stats):
    """Return the subset of `items` that survive verification, with keys fixed where needed."""
    if not items:
        return []
    res = gem.ask_json(
        VERIFY_PROMPT.replace("<<QUESTIONS>>", fmt_for_check(items)),
        model=gem.verify_model, temperature=0.0)
    rows = {}
    for r in (res.get("results", []) if isinstance(res, dict) else []):
        try:
            rows[int(r.get("n"))] = r
        except (TypeError, ValueError, AttributeError):
            continue

    disputed = []  # (index, checker_letter, issue)
    for i, it in enumerate(items, 1):
        r = rows.get(i)
        checker = to_letter(r.get("answer")) if r else None
        issue = (r.get("issue") if r else "no_check_result") or None
        if checker == it["answer"] and not issue:
            continue
        disputed.append((i, checker, issue))

    verdict = {}  # index -> final letter or None (invalid)
    if disputed:
        sub = [items[i - 1] for i, _, _ in disputed]
        extra = [{"author_key": items[i - 1]["answer"], "checker_answer": c, "checker_issue": iss}
                 for i, c, iss in disputed]
        arb = gem.ask_json(
            ARBITRATE_PROMPT.replace("<<QUESTIONS>>", fmt_for_check(sub, extra)),
            model=gem.verify_model, temperature=0.0)
        arows = {}
        for r in (arb.get("results", []) if isinstance(arb, dict) else []):
            try:
                arows[int(r.get("n"))] = r
            except (TypeError, ValueError, AttributeError):
                continue
        for k, (i, checker, issue) in enumerate(disputed, 1):
            r = arows.get(k)
            final = to_letter(r.get("final")) if r else None  # INVALID / missing -> None
            verdict[i] = (final, (r or {}).get("reason", "no arbitration result"), checker, issue)

    kept = []
    for i, it in enumerate(items, 1):
        if i not in verdict:
            it["v"] = True
            bump(stats, "verified_clean")
            kept.append(it)
            continue
        final, reason, checker, issue = verdict[i]
        base = {"mock": mid, "q": it["q"], "options": it["options"],
                "author_key": it["answer"], "checker": checker, "issue": issue, "reason": reason}
        if final is None:
            bump(stats, "dropped_invalid")
            log_review(dict(base, action="dropped"))
            continue
        if final != it["answer"]:
            bump(stats, "key_fixed")
            log_review(dict(base, action="key_fixed", old_key=it["answer"], new_key=final))
            it["answer"] = final
        else:
            bump(stats, "key_confirmed_after_dispute")
            log_review(dict(base, action="confirmed"))
        it["v"] = True
        kept.append(it)
    return kept


# --------------------------------------------------------------------------
# Build one mock
# --------------------------------------------------------------------------
def build_mock(gem, subject_no, mock, seen, verify, max_rounds=MAX_ROUNDS):
    mid, title, focus, count = mock
    subj = SUBJECTS[subject_no]
    cache = load_cache(mid)
    good = [q for q in cache.get("questions", []) if clean_item(q)]
    stats = cache.setdefault("stats", {})
    for q in good:
        seen.add(q["q"], q["options"], subject_no)

    print(f"[{mid}] {title}  (target {count}, cached {len(good)})", flush=True)
    rounds = 0
    while True:
        if verify:
            pending = [q for q in good if not q.get("v")]
            if pending:
                print(f"    verifying {len(pending)} questions", flush=True)
                good = [q for q in good if q.get("v")] + verify_items(gem, mid, pending, stats)
                cache["questions"] = good
                save_cache(mid, cache)
        if len(good) >= count or rounds >= max_rounds:
            break

        need = count - len(good)
        ask = need + (max(2, need // 10) if rounds == 0 else 2)
        prompt = (GEN_PROMPT
                  .replace("<<SUBJECT>>", subj["name"])
                  .replace("<<TITLE>>", title)
                  .replace("<<FOCUS>>", focus)
                  .replace("<<N>>", str(ask))
                  .replace("<<PREVIOUS>>", "\n".join(f"- {s}" for s in seen.stems(subject_no)) or "(none yet)"))
        print(f"    generating {ask} (round {rounds + 1})", flush=True)
        raw = gem.ask_json(prompt, temperature=0.8)
        items = raw.get("questions", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
        new = []
        for it in items:
            c = clean_item(it)
            if not c:
                bump(stats, "rejected_format")
                continue
            c["v"] = False
            if seen.is_dup(c["q"], c["options"]):
                bump(stats, "rejected_duplicate")
                continue
            seen.add(c["q"], c["options"], subject_no)
            new.append(c)
        new = new[:need]
        bump(stats, "generated", len(new))
        good += new
        cache["questions"] = good
        save_cache(mid, cache)
        rounds += 1

    if len(good) < count:
        print(f"    INCOMPLETE: {len(good)}/{count}; re-run to top up", flush=True)
        return False

    good = good[:count]
    final = finalize_items(good, mid)
    atomic_write(bank_file(subject_no, mock), render_md(subj["name"], title, final))
    dist = Counter(it["answer"] for it in final)
    stats["answer_distribution"] = dict(sorted(dist.items()))
    stats["levels"] = dict(Counter(it["level"] for it in final))
    stats["unverified"] = sum(1 for q in good if not q.get("v"))
    cache["questions"] = good
    save_cache(mid, cache)
    print(f"    done: {len(final)} questions, answers {dict(sorted(dist.items()))}", flush=True)
    return True


# --------------------------------------------------------------------------
# Master + status files
# --------------------------------------------------------------------------
def write_master(subject_no):
    subj = SUBJECTS[subject_no]
    parts = []
    for mock in subj["mocks"]:
        f = bank_file(subject_no, mock)
        if f.exists():
            parts.append(f.read_text(encoding="utf-8").rstrip("\n"))
    if parts:
        atomic_write(BANK / subj["slug"] / f"_MASTER_{subj['slug']}.md", "\n\n".join(parts) + "\n")


def write_status():
    lines = ["# HARTRON DEO bank status", ""]
    grand_done = grand_target = 0
    for no, subj in SUBJECTS.items():
        lines += [f"## Subject {no}: {subj['name']}", "",
                  "| Mock | Title | Target | Done | Answer split | Fixed keys | Dropped | Unverified |",
                  "|---|---|---|---|---|---|---|---|"]
        done_total = 0
        for mock in subj["mocks"]:
            mid, title, _, count = mock
            f = bank_file(no, mock)
            done = 0
            if f.exists():
                done = len(parse_md(f.read_text(encoding="utf-8"))[0])
            c = load_cache(mid)
            st = c.get("stats", {})
            lines.append(
                f"| {mid} | {title} | {count} | {done if done else '-'} | "
                f"{json.dumps(st.get('answer_distribution', {})) if done else ''} | "
                f"{st.get('key_fixed', 0)} | {st.get('dropped_invalid', 0)} | {st.get('unverified', 0) if done else ''} |")
            done_total += done
        lines += ["", f"Subject {no}: {done_total}/{subj['target']} questions", ""]
        grand_done += done_total
        grand_target += subj["target"]
    lines.append(f"**Total: {grand_done}/{grand_target}**")
    atomic_write(BANK / "STATUS.md", "\n".join(lines) + "\n")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(description="HARTRON DEO question bank generator")
    p.add_argument("--shift", type=int, choices=[1, 2], help="1 = Subject 1, 2 = Subject 2")
    p.add_argument("--only", default="", help="comma-separated mock ids, e.g. S1_03,S1_04")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--verify-model", default=os.environ.get("QBANK_VERIFY_MODEL", ""))
    p.add_argument("--rpm", type=int, default=int(os.environ.get("QBANK_RPM", "5")))
    p.add_argument("--no-verify", action="store_true")
    p.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    p.add_argument("--time-budget-min", type=float, default=330)
    p.add_argument("--dry-run", action="store_true", help="show the plan, no API calls")
    p.add_argument("--check", action="store_true", help="validate the topic map and exit")
    p.add_argument("--status", action="store_true", help="rebuild master + STATUS files and exit")
    return p.parse_args(argv)


def main(argv=None, gem_factory=None):
    args = parse_args(argv)
    validate_config()
    if args.check:
        for no, s in SUBJECTS.items():
            print(f"Subject {no}: {len(s['mocks'])} mocks, {sum(m[3] for m in s['mocks'])} questions")
        print("topic map OK")
        return 0
    if args.status:
        for no in SUBJECTS:
            write_master(no)
        write_status()
        print("status rebuilt")
        return 0
    if not args.shift:
        print("error: --shift 1 or 2 is required", file=sys.stderr)
        return 1

    subject_no = args.shift
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    mocks = [m for m in SUBJECTS[subject_no]["mocks"] if not only or m[0] in only]
    if only and not mocks:
        print(f"error: no mock matches {sorted(only)}", file=sys.stderr)
        return 1

    todo = [m for m in mocks if not is_done(subject_no, m)]
    print(f"Subject {subject_no}: {len(mocks)} mocks selected, {len(todo)} to do, "
          f"{sum(m[3] for m in todo)} questions", flush=True)
    if args.dry_run:
        for m in mocks:
            print(f"  {m[0]} {'done' if is_done(subject_no, m) else 'todo'}  {m[3]:>3}  {m[1]}")
        return 0
    if not todo:
        print("nothing to do")
        write_master(subject_no)
        write_status()
        return 0

    if gem_factory is None:
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            print("error: GEMINI_API_KEY is not set", file=sys.stderr)
            return 1
        gem = Gemini(key, args.model, args.verify_model or None, args.rpm)
    else:
        gem = gem_factory(args)

    seen = load_seen()
    started = time.monotonic()
    incomplete, exit_code = [], 0
    try:
        for mock in todo:
            if (time.monotonic() - started) / 60 > args.time_budget_min:
                print("::warning::time budget reached; stopping cleanly. Re-run to continue.")
                break
            try:
                ok = build_mock(gem, subject_no, mock, seen, not args.no_verify, args.max_rounds)
            except RuntimeError as e:  # repeated bad output etc: skip this mock, keep going
                print(f"::warning::{mock[0]} skipped this run: {e}", flush=True)
                ok = False
            if not ok:
                incomplete.append(mock[0])
    except QuotaExhausted as e:
        print(f"::warning::API quota exhausted ({e}). Progress is saved. Re-run after the quota resets "
              "(daily quota resets at midnight Pacific time).")
    except FatalAPIError as e:
        print(f"::error::{e}")
        exit_code = 1
    finally:
        write_master(subject_no)
        write_status()

    remaining = [m[0] for m in mocks if not is_done(subject_no, m)]
    print(f"API calls this run: {gem.calls}")
    print(f"Remaining mocks: {remaining if remaining else 'none - subject complete'}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
