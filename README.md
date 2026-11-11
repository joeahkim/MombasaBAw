# Mombasa Business Awards

Automated voter for the [Mombasa Business Awards](https://mombasabusinessawards.kenyachamber.co.ke/vote/). Votes for a list of nominees across multiple categories, using multiple accounts, each on its own randomised schedule (every **2 h 03 m to 2 h 15 m**), and respects the site's own time-lock messages when it tells us to wait.

Runs as a **long-lived daemon**: start it once, leave it running, `Ctrl+C` to stop.

---

## Table of contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration: `details.txt`](#configuration-detailstxt)
- [Running the bot](#running-the-bot)
- [Command-line options](#command-line-options)
- [How scheduling works](#how-scheduling-works)
- [Files created at runtime](#files-created-at-runtime)
- [Stopping the bot](#stopping-the-bot)

---

## Requirements

- **Python 3.8+**
- **Google Chrome** installed and up to date
- **Internet connection**
- (Optional) `git`, if you want to clone instead of downloading a zip

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/joeahkim/MombasaBAw.git
cd MombasaBAw
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv venv
venv\Scripts\Activate
```

**macOS / Linux:**

```bash
python -m venv venv
source venv/bin/activate
```

You'll see `(venv)` in the prompt once it's active.

### 3. Install dependencies

```bash
pip install selenium webdriver-manager
```

That's all that's needed. `webdriver-manager` will fetch the correct `chromedriver` for your installed Chrome on first run, so no manual download is required.

---

## Configuration: `details.txt`

Each account is one `[RECORD_ID]` block in `details.txt`, next to `mba.py`:

```
# One [RECORD_ID] block per account. Each block needs Email and Phone.
# The [ID] is any unique, stable label. It becomes the state key in
# vote_state.json and the per-account Chrome profile folder name, so
# keep it the same across runs. Using the email as the ID is convenient
# for --account lookups (e.g. python mba.py --account john.doe@gmail.com).

[TEST_RECORD_1]
Email: sample1@example.com
Phone: +254700000000

[TEST_RECORD_2]
Email: sample2@example.com
Phone: +254711111111
```

Rules:

| Field         | Required | Notes                                                                  |
| ------------- | -------- | ---------------------------------------------------------------------- |
| `[RECORD_ID]` | yes      | Any unique, stable label. Avoid reusing IDs from old runs.             |
| `Email`       | yes      | Must be a valid email format. Duplicates across accounts are rejected. |
| `Phone`       | yes      | E.g. `+254700000000` or `0714563242`.                                  |

Lines starting with `#` are comments and are ignored. Duplicate IDs or emails will cause the bot to refuse to start with a clear error.

You can add or remove accounts between runs; the daemon re-reads `details.txt` every poll, so edits take effect without restarting.

---

## Running the bot

### Daemon mode (default and recommended)

```bash
python mba.py
```

The bot will:

1. Load `details.txt` and `vote_state.json`.
2. For each account, check whether it's due.
3. For each **due** account:
   - Launch a fresh Chrome with that account's own persistent profile.
   - Vote for every nominee in `SECTIONS`.
   - Record the vote time and set the account's next vote to `now + random(2h03m … 2h15m)`.
   - Close the browser.
4. Compute the earliest future `next_vote_at` across all accounts and **sleep until then** (polling every 5 min so edits to `details.txt` are picked up).
5. Repeat forever.

You'll see something like:

```
[2026-11-11 11:22:07] SESSION START
[2026-11-11 11:22:07] Processing 2 due account(s): ['TEST_RECORD_1', 'TEST_RECORD_2']
[2026-11-11 11:22:07] [TEST_RECORD_1] Starting vote run for sample1@example.com
[2026-11-11 11:22:09] [TEST_RECORD_1] Opening https://mombasabusinessawards.kenyachamber.co.ke/vote/
[2026-11-11 11:22:12] [TEST_RECORD_1] CEO of The Year section found.
[2026-11-11 11:22:14] [TEST_RECORD_1] Intrasoft Technologies found.
[2026-11-11 11:22:14] [TEST_RECORD_1] Clicked Vote for Intrasoft Technologies.
[2026-11-11 11:22:16] [TEST_RECORD_1] Filled email='sample1@example.com', phone='+254700000000'.
[2026-11-11 11:22:16] [TEST_RECORD_1] Clicked submit.
[2026-11-11 11:22:18] [TEST_RECORD_1] Vote form closed for Intrasoft Technologies: vote accepted.
...
[2026-11-11 11:23:02] [TEST_RECORD_1] Recorded 6 vote(s); next at 2026-11-11T13:27:44 (+2h04m11s).
[2026-11-11 11:23:02] [TEST_RECORD_1] Browser closed.
[2026-11-11 11:23:02] [TEST_RECORD_1] Run complete: 6/6 votes accepted.
[2026-11-11 11:23:02] [TEST_RECORD_2] Starting vote run for sample2@example.com
...
[2026-11-11 11:24:10] Pass complete: 12/12 votes; time-locked: none.
[2026-11-11 11:24:10] Next due at 2026-11-11 13:27:44 (2h03m34s from now). Sleeping up to 5m00s per poll.
```

While idle, the bot only prints the "Next due at …" line when the target time changes, so the log stays quiet.

### One-shot mode (single pass, then exit)

```bash
python mba.py --once
```

Useful for testing or for wiring into an external scheduler (Task Scheduler, cron). Runs one pass over due accounts, then exits with:

- `0` for done or nothing was due
- `1` for pass ran but every vote failed
- `3` for `--account` not found in `details.txt`
- `4` for `details.txt` missing or invalid

### Inspect schedule without voting

```bash
python mba.py --status
```

Prints JSON like:

```json
{
  "accounts": {
    "TEST_RECORD_1": {
      "due": false,
      "email": "sample1@example.com",
      "history_count": 6,
      "interval_seconds": 7451,
      "last_vote_at": "2026-11-11T11:23:02",
      "next_vote_at": "2026-11-11T13:27:13",
      "reason": "not due until 2026-11-11 13:27:13 (2h03m11s from now)",
      "time_lock_message": null
    }
  },
  "profile_root": "...\\chrome_profiles",
  "state_path": "...\\vote_state.json"
}
```

No browser is launched.

---

## Command-line options

| Flag           | Description                                                                                                           |
| -------------- | --------------------------------------------------------------------------------------------------------------------- |
| _(none)_       | **Daemon mode**: run forever, voting on schedule.                                                                     |
| `--once`       | Single pass, then exit.                                                                                               |
| `--status`     | Print per-account schedule state, exit.                                                                               |
| `--account ID` | Only process this `[RECORD_ID]`. Works with daemon or `--once`.                                                       |
| `--force`      | Ignore schedule gate. In daemon mode only affects the first pass, to prevent runaway re-voting.                       |
| `--poll N`     | Seconds between idle wake-ups (default `300`). Lower = faster pickup of `details.txt` edits; higher = fewer wake-ups. |
| `--pause`      | Prompt before closing each browser (debugging only).                                                                  |

---

## How scheduling works

Each account has its own independent schedule, stored in `vote_state.json`:

- **First run**: account has no record, so it's treated as due immediately.
- **After a successful run**: `next_vote_at = now + random(7,380 s … 8,100 s)` i.e. **2 h 03 m to 2 h 15 m**.
- **After a time-lock**: `next_vote_at = <parsed time from the message> + 60 s buffer`.

The daemon always picks the **earliest** future `next_vote_at` across all accounts and sleeps until then (capped at `--poll` so it wakes periodically to reload `details.txt` and to recover from clock drift).

Because state is persisted to disk after each account finishes, killing and restarting the process **does not reset the schedule**; it resumes exactly where it stopped.

---

## Files created at runtime

| Path                    | Purpose                                                                                                                        |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `vote_state.json`       | Per-account schedule, last vote time, interval, history (last 50), time-lock info.                                             |
| `chrome_profiles/<ID>/` | One isolated Chrome profile per account. Holds cookies, `localStorage`, and the form details the site remembers between votes. |

**Do not delete either during normal operation.** If you need a clean slate for one account:

```bash
rm -rf chrome_profiles/TEST_RECORD_1
```

Then edit `vote_state.json` and remove the `TEST_RECORD_1` block (or just delete the whole file to reset everything). The next run recreates both.

`chrome_profiles/` can grow over time (each profile is ~50 to 150 MB). Deleting accounts you no longer need is safe.

---

## Stopping the bot

Press **`Ctrl+C`** in the terminal:

- The currently running account finishes its pass (or is interrupted at the next wait).
- The browser for the current account is closed.
- State for completed accounts is already saved.
- The process exits cleanly.

Restart with `python mba.py` and it resumes from the persisted schedule with no votes missed and no duplicates.
