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

Pick the model from the dropdown. To use a model that is not in the list, type its name in
"custom_model" (it overrides the dropdown).

**Where the files are**
1. In the repo itself: open the `bank` folder -> `subject1` / `subject2`. One `.md` per finished
   mock, plus `_MASTER_subject1.md` / `_MASTER_subject2.md` (all mocks of that subject in one file).
2. As a download: open the finished run in the Actions tab, scroll to the bottom to "Artifacts",
   click `HARTRON-DEO-subjectN-questions`. The zip contains every finished mock `.md`,
   the master file, `STATUS.md` and `review_log.jsonl`.
3. At the top of the run page, the status table shows which mocks are done.

A mock only gets its `.md` file once it is complete (all questions generated and verified).
If you only see `STATUS.md` and the log, no mock finished in that run: open the "Generate shift"
step log to see why (usually the free-tier quota; re-run to continue).

`review/review_log.jsonl` is only a log of questions the verifier disputed. Not part of the bank.

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
