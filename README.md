# HARTRON DEO question bank generator

1,500 MCQs: Subject 1 (750) + Subject 2 (750), 44 mocks of 25-50 questions each, in your
`# MOCK / ## EN / ## ANSWERS` markdown format. Runs on GitHub Actions with Gemini.

## One-time setup

1. Create a **private** GitHub repo (e.g. `deo-bank`).
2. Upload everything from this zip to the repo root. The workflow file must end up at
   `.github/workflows/generate.yml`. If you upload by browser, use "Create new file" and type that path.
3. Get a key at https://aistudio.google.com/apikey.
4. Repo -> Settings -> Secrets and variables -> Actions -> New repository secret:
   name `GEMINI_API_KEY`, value = your key.
5. Repo -> Settings -> Actions -> General -> Workflow permissions -> **Read and write permissions** -> Save.

## Running a shift

Actions tab -> "Generate HARTRON DEO question bank" -> Run workflow -> pick shift 1 or 2.

- Output lands in `bank/subject1/` and `bank/subject2/` (one `.md` per mock + `_MASTER_subjectN.md`).
- `bank/STATUS.md` shows progress per mock, answer-key split and how many keys were fixed.
- `review/review_log.jsonl` lists every question the verifier disputed, and what was done.
- The same files are also attached to the run as a downloadable artifact.

## Regenerating with the improved rules (v2)

Run each shift once with **force = true**. That deletes the existing mocks for the selected set and
rebuilds them (old versions stay in git history). Later runs: leave force off so quota-limited runs resume.
Do NOT leave force on when re-running to resume, or it wipes progress each time.

v2 changes: answer-position balance now also covers numeric options; "correct option is the longest"
questions are rejected and the prompt forbids length cues; two independent verification solves (normal and
reversed option order) with arbitration on any disagreement; stricter rules for formulas, shortcuts, HTML5 and
"which is NOT" questions; near-duplicate wording is caught; each mock ends with a `## EXPLANATIONS` section
(set QBANK_EXPLAIN=0 to switch off). STATUS.md now shows "Correct=longest %" per mock; aim for under 35.
API use is higher (about 70-110 calls per shift), so a shift may take two days on the free tier.

## Free tier and resuming

Gemini free-tier limits change often and can be low (daily request caps). The script handles this:

- When the quota runs out it stops cleanly, commits everything done so far, and exits.
- Run the same shift again later (quota resets at midnight Pacific time = 12:30 PM IST).
  Finished mocks are skipped, half-finished mocks resume from `cache/`.
- A shift needs roughly 50-80 API calls (generate + verify + arbitration, plus top-ups).
  If your daily cap is lower than that, the shift simply takes more than one day.
- Calls are paced at 5 per minute by default. Change with `QBANK_RPM` if your limit differs.

## What the pipeline does per mock

1. Asks Gemini for the questions as JSON (so nothing depends on fragile text parsing).
2. Rejects bad items: wrong option count, "All of the above" style options, label clashes.
3. Removes duplicates against every question already in the bank (both subjects).
4. Verification: a second pass solves each question without seeing the key. Any mismatch or
   flagged question goes to an arbitration pass. Result: key fixed, or question dropped as
   ambiguous.
5. Tops up any gaps with fresh questions (up to 5 rounds), verifying those too.
6. Sorts easy -> moderate -> hard, shuffles option order so answers are balanced across A-D,
   writes the markdown.

## Useful commands (local)

```
pip install -r requirements.txt
python generate.py --check                  # validate topic map and totals
python generate.py --shift 1 --dry-run      # show what would run
python generate.py --shift 1 --only S1_01   # run a single mock
python generate.py --status                 # rebuild master and status files
export GEMINI_API_KEY=...                   # needed for real runs
```

Change the split in `topics.py`. Keep each mock at 25-50 and each subject total at 750
(or change `target`), then run `--check`.

## Before you sell it

Verification is a second AI opinion, not a human check. Spot-check a sample from each mock,
especially IT Policy (S1_23), Excel formula-output questions (S2_14) and shortcut questions.
HTML questions contain tags such as `<p>`; make sure `target1st-pdf-generator.html` escapes
them instead of rendering them.
