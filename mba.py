from datetime import datetime, timedelta
import argparse
import json
import os
import random
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from details import load_details


URL = "https://mombasabusinessawards.kenyachamber.co.ke/vote/"

SECTIONS = (
    (
        "CEO of The Year",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[2]/div/h3',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[2]/div/ul/li[14]',
        "Intrasoft Technologies",
        '//*[@id="scroll"]/section[2]/div/div[3]/div[2]/div/ul/li[14]/button',
        True,
    ),
    (
        "Most Innovative Business",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[3]/div/h3',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[3]/div/ul/li[13]',
        "Intrasoft Technologies",
        '//*[@id="scroll"]/section[2]/div/div[3]/div[3]/div/ul/li[13]/button',
        False,
    ),
    (
        "Best in Corporate Social Responsibility",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[15]/div/h3',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[15]/div/ul/li[4]',
        "Hazina Group Foundation",
        '//*[@id="scroll"]/section[2]/div/div[3]/div[15]/div/ul/li[4]/button',
        False,
    ),
    (
        "Best SME",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[20]/div/h3',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[20]/div/ul/li[15]',
        "INTRASOFT TECHNOLOGIES LIMITED",
        '//*[@id="scroll"]/section[2]/div/div[3]/div[20]/div/ul/li[15]/button',
        False,
    ),
    (
        "Best Innovation & Social Impact Hub",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[26]/div/h3',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[26]/div/ul/li[2]',
        "HAZINA GROUP FOUNDATION",
        '//*[@id="scroll"]/section[2]/div/div[3]/div[26]/div/ul/li[2]/button',
        False,
    ),
    (
        "Most Inclusive Enterprise",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[35]/div/h3',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[35]/div/ul/li[3]',
        "HAZINA GROUP FOUNDATION",
        '//*[@id="scroll"]/section[2]/div/div[3]/div[35]/div/ul/li[3]/button',
        False,
    ),
)

VOTE_EMAIL_XPATH = '//*[@id="vote-email"]'
VOTE_PHONE_XPATH = '//*[@id="vote-phone"]'
VOTE_SUBMIT_XPATH = '//*[@id="vote-submit"]'
VOTE_FORM_XPATH = '//*[@id="vote-form"]'
VOTE_FORM_DISMISS_XPATH = '//*[@id="vote-form"]/div[1]/button'

VOTE_FORM_DISAPPEAR_TIMEOUT = 10
VOTE_FORM_ERROR_TIMEOUT = 5

ERROR_TEXT_XPATHS = (
    '//*[@id="vote-form-error"]',
    '//*[@id="vote-form"]/div[2]/div[2]/div',
    '//*[@id="vote-form"]//*[contains(@class, "error")]',
    '//*[@id="vote-form"]//*[contains(@class, "invalid")]',
    '//*[@id="vote-form"]//*[@role="alert"]',
    '//*[@id="vote-error"]',
    '//*[@id="vote-form"]//*[contains(@class, "message")]',
)

STATE_PATH = Path(__file__).with_name("vote_state.json")
PROFILE_ROOT = Path(__file__).with_name("chrome_profiles")

MIN_INTERVAL_SECONDS = 2 * 3600 + 3 * 60    # 2h03m
MAX_INTERVAL_SECONDS = 2 * 3600 + 15 * 60   # 2h15m
HISTORY_LIMIT = 50

TIME_LOCK_BUFFER_SECONDS = 60

# How often the daemon wakes up while waiting for the next due time.
# Small enough to pick up edits to details.txt / vote_state.json quickly,
# large enough not to burn CPU.
DEFAULT_POLL_SECONDS = 300   # 5 min

# Minimum cooldown after a pass so that transient failures (no time-lock)
# don't cause a tight retry loop.
MIN_COOLDOWN_SECONDS = 300   # 5 min


class VoteTimeLock(Exception):
    """Raised when the vote form returns a time-lock error."""

    def __init__(self, wait_until, message):
        self.wait_until = wait_until
        self.message = message
        super().__init__(
            f"Time-lock until {wait_until:%Y-%m-%d %H:%M:%S}: {message}"
        )


def _now():
    return datetime.now()


def log(message):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


def _format_delta(seconds):
    seconds = int(max(0, seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}h{minutes:02d}m{secs:02d}s"


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _profile_dir_for(account):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", account["id"]) or "default"
    return PROFILE_ROOT / safe


def load_state():
    if not STATE_PATH.exists():
        return {"accounts": {}}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        log(f"Could not read state file {STATE_PATH}: {error}. Starting fresh.")
        return {"accounts": {}}
    if not isinstance(data, dict):
        log(f"State file {STATE_PATH} is not a JSON object. Starting fresh.")
        return {"accounts": {}}
    if not isinstance(data.get("accounts"), dict):
        if any(k in data for k in ("last_vote_at", "next_vote_at", "interval_seconds")):
            log(
                f"Found legacy single-account state in {STATE_PATH}; "
                "starting fresh with per-account state."
            )
        return {"accounts": {}}
    return data


def save_state(state):
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = STATE_PATH.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(state, indent=2, sort_keys=True), encoding="utf-8"
        )
        os.replace(tmp_path, STATE_PATH)
    except OSError as error:
        log(f"Could not write state file {STATE_PATH}: {error}")


def pick_interval_seconds():
    return random.randint(MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS)


def record_account_run(state, account, votes):
    if not votes:
        return
    key = account["id"]
    now = _now()

    accounts = state.setdefault("accounts", {})
    if not isinstance(accounts, dict):
        accounts = {}
        state["accounts"] = accounts
    entry = accounts.setdefault(key, {"history": []})
    if not isinstance(entry, dict):
        entry = {"history": []}
        accounts[key] = entry

    entry["record_id"] = account["id"]
    entry["email"] = account["Email"]

    history = entry.setdefault("history", [])
    if not isinstance(history, list):
        history = []
        entry["history"] = history
    for section, nominee in votes:
        history.append(
            {
                "at": now.isoformat(timespec="seconds"),
                "section": section,
                "nominee": nominee,
            }
        )
    del history[:-HISTORY_LIMIT]

    interval = pick_interval_seconds()
    entry["last_vote_at"] = now.isoformat(timespec="seconds")
    entry["last_vote_section"] = votes[-1][0]
    entry["last_vote_nominee"] = votes[-1][1]
    entry["interval_seconds"] = interval
    entry["next_vote_at"] = (
        now + timedelta(seconds=interval)
    ).isoformat(timespec="seconds")
    entry.pop("time_lock_message", None)
    entry.pop("time_lock_at", None)

    save_state(state)
    log(
        f"[{account['id']}] Recorded {len(votes)} vote(s); "
        f"next at {entry['next_vote_at']} (+{_format_delta(interval)})."
    )


def record_time_lock(state, account, successes, wait_until, message):
    if successes:
        record_account_run(state, account, successes)

    key = account["id"]
    accounts = state.setdefault("accounts", {})
    if not isinstance(accounts, dict):
        accounts = {}
        state["accounts"] = accounts
    entry = accounts.setdefault(key, {"history": []})
    if not isinstance(entry, dict):
        entry = {"history": []}
        accounts[key] = entry

    entry["record_id"] = account["id"]
    entry["email"] = account["Email"]
    effective = wait_until + timedelta(seconds=TIME_LOCK_BUFFER_SECONDS)
    entry["next_vote_at"] = effective.isoformat(timespec="seconds")
    entry["time_lock_message"] = message
    entry["time_lock_at"] = _now().isoformat(timespec="seconds")

    save_state(state)
    log(
        f"[{account['id']}] Time-lock saved. "
        f"Next vote at {entry['next_vote_at']} "
        f"(+{TIME_LOCK_BUFFER_SECONDS}s buffer)."
    )


def account_due(state, account, force=False):
    entry = state.get("accounts", {}).get(account["id"])
    if not isinstance(entry, dict):
        return True, "no previous vote recorded"
    next_dt = _parse_dt(entry.get("next_vote_at"))
    if next_dt is None:
        return True, "no next_vote_at recorded"
    remaining = (next_dt - _now()).total_seconds()
    if remaining <= 0:
        return True, f"due (scheduled at {next_dt:%Y-%m-%d %H:%M:%S})"
    if force:
        return True, f"forced (would be due at {next_dt:%Y-%m-%d %H:%M:%S})"
    suffix = ""
    if entry.get("time_lock_message"):
        suffix = f" [time-locked: {entry['time_lock_message']!r}]"
    return (
        False,
        f"not due until {next_dt:%Y-%m-%d %H:%M:%S} "
        f"({_format_delta(remaining)} from now){suffix}",
    )


def compute_next_wake(state, accounts, max_sleep):
    """Return (sleep_seconds, next_due_dt_or_None).

    - If any account is due now → (0, None).
    - Else → (min(time_until_earliest, max_sleep), earliest_dt).
    - If no account has a schedule (edge case) → (max_sleep, None).
    """
    now = _now()
    earliest = None
    for account in accounts:
        entry = state.get("accounts", {}).get(account["id"])
        next_dt = _parse_dt(entry.get("next_vote_at")) if isinstance(entry, dict) else None
        if next_dt is None:
            return 0, None
        if next_dt <= now:
            return 0, None
        if earliest is None or next_dt < earliest:
            earliest = next_dt
    if earliest is None:
        return max_sleep, None
    delta = (earliest - now).total_seconds()
    return min(delta, max_sleep), earliest


def build_driver(account):
    profile = _profile_dir_for(account)
    profile.mkdir(parents=True, exist_ok=True)

    options = webdriver.ChromeOptions()
    # Existing: per-account persistent profile so stored form details survive.
    options.add_argument(f"--user-data-dir={profile}")
    options.add_argument("--profile-directory=Default")

    # Anti-automation fingerprints.
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options,
    )
    driver.maximize_window()

    # Hide navigator.webdriver and related properties at the JS level.
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => false});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                window.chrome = window.chrome || { runtime: {} };
                const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
                if (originalQuery) {
                    window.navigator.permissions.query = (parameters) =>
                        parameters.name === 'notifications'
                            ? Promise.resolve({ state: Notification.permission })
                            : originalQuery(parameters);
                }
            """
        },
    )

    return driver


def find_section(driver, name, section_xpaths):
    for xpath in section_xpaths:
        try:
            section = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", section
            )
            log(f"{name} section found.")
            time.sleep(3)
            return section
        except TimeoutException:
            continue
    log(f"{name} section not found.")
    return None


def find_nominee(driver, nominee_xpath, nominee_name):
    try:
        nominee = WebDriverWait(driver, 10).until(
            lambda browser: next(
                (
                    element
                    for element in browser.find_elements(By.XPATH, nominee_xpath)
                    if element.is_displayed()
                ),
                False,
            )
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", nominee
        )
        time.sleep(3)
        nominee_text = " ".join(
            (nominee.get_attribute("textContent") or nominee.text)
            .replace("\xa0", " ")
            .split()
        )
        if nominee_name.casefold() in nominee_text.casefold():
            log(f"{nominee_name} found.")
            return nominee
        log(f"{nominee_name} not found. Element text: {nominee_text!r}")
    except TimeoutException:
        log(f"{nominee_name} not found.")
    return None


def _collect_error_text(driver):
    found = []
    for xpath in ERROR_TEXT_XPATHS:
        try:
            for element in driver.find_elements(By.XPATH, xpath):
                if not element.is_displayed():
                    continue
                text = " ".join(
                    (element.get_attribute("textContent") or element.text)
                    .replace("\xa0", " ")
                    .split()
                )
                if text and text not in found:
                    found.append(text)
        except WebDriverException:
            continue
    return " | ".join(found)


def _parse_time_from_message(message):
    if not message:
        return None

    now = _now()

    match = re.search(r"(\d{1,2}):(\d{2})\s*([AaPp]\.?[Mm]\.?)?", message)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        ampm = match.group(3)
    else:
        match = re.search(r"(\d{1,2})\s*([AaPp]\.?[Mm]\.?)", message)
        if match:
            hour = int(match.group(1))
            minute = 0
            ampm = match.group(2)
        else:
            match = re.search(r"(\d+)\s+hours?", message)
            if match:
                return now + timedelta(hours=int(match.group(1)))
            return None

    if ampm:
        ampm_clean = ampm.replace(".", "").upper()
        if ampm_clean == "PM" and hour < 12:
            hour += 12
        elif ampm_clean == "AM" and hour == 12:
            hour = 0

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        if (now - candidate).total_seconds() <= 60:
            candidate = now + timedelta(seconds=MIN_INTERVAL_SECONDS)
        else:
            candidate += timedelta(days=1)

    return candidate


def cast_vote(driver, nominee_name, vote_button_xpath, details=None):
    try:
        vote_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, vote_button_xpath))
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", vote_button
        )
        vote_button.click()
        log(f"Clicked Vote for {nominee_name}.")
    except TimeoutException:
        log(f"Vote button not clickable for {nominee_name}.")
        return False

    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, VOTE_FORM_XPATH))
        )
        submit_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, VOTE_SUBMIT_XPATH))
        )
    except TimeoutException:
        log("Vote form or submit button did not appear.")
        return False

    if details is not None:
        try:
            email_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, VOTE_EMAIL_XPATH))
            )
            phone_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, VOTE_PHONE_XPATH))
            )
        except TimeoutException:
            log("Email/phone fields did not appear.")
            return False
        email_field.clear()
        email_field.send_keys(details["Email"])
        phone_field.clear()
        phone_field.send_keys(details["Phone"])
        log(f"Filled email={details['Email']!r}, phone={details['Phone']!r}.")
    else:
        log("Skipping field fill — using details stored on the page.")

    try:
        submit_button.click()
        log("Clicked submit.")
    except (NoSuchElementException, WebDriverException) as error:
        log(f"Submit click failed: {error}")
        return False

    try:
        WebDriverWait(driver, VOTE_FORM_DISAPPEAR_TIMEOUT).until(
            EC.invisibility_of_element_located((By.XPATH, VOTE_FORM_XPATH))
        )
        log(f"Vote form closed for {nominee_name} — vote accepted.")
        return True
    except TimeoutException:
        log(
            f"Vote form still visible after submit for {nominee_name} — "
            "checking for error."
        )

    error_text = ""
    try:
        error_text = WebDriverWait(driver, VOTE_FORM_ERROR_TIMEOUT).until(
            lambda browser: _collect_error_text(browser) or False
        )
    except TimeoutException:
        error_text = _collect_error_text(driver)

    if error_text:
        log(f"Vote error for {nominee_name}: {error_text!r}")
    else:
        log(f"Vote form still visible for {nominee_name} but no error text found.")

    wait_until = _parse_time_from_message(error_text)
    if wait_until is not None:
        log(
            f"Detected time-lock until {wait_until:%Y-%m-%d %H:%M:%S} — "
            "aborting account run (browser will close)."
        )
        raise VoteTimeLock(wait_until, error_text)

    try:
        dismiss_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, VOTE_FORM_DISMISS_XPATH))
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", dismiss_button
        )
        dismiss_button.click()
        log("Clicked dismiss button on the vote form.")
        try:
            WebDriverWait(driver, 5).until(
                EC.invisibility_of_element_located((By.XPATH, VOTE_FORM_XPATH))
            )
            log("Vote form dismissed.")
        except TimeoutException:
            log("Vote form still visible after dismiss click.")
    except TimeoutException:
        log('Dismiss button //*[@id="vote-form"]/div[1]/button not clickable.')

    return False


def vote_account(account, state, pause=False):
    log(f"[{account['id']}] Starting vote run for {account['Email']}")
    driver = None
    successes = []
    attempted = 0
    time_locked = False
    try:
        driver = build_driver(account)
        driver.maximize_window()
        log(f"[{account['id']}] Opening {URL}")
        driver.get(URL)
        WebDriverWait(driver, 20).until(
            lambda browser: browser.execute_script("return document.readyState")
            == "complete"
        )

        for (
            name,
            section_xpaths,
            nominee_xpath,
            nominee_name,
            vote_xpath,
            fill_details,
        ) in SECTIONS:
            if find_section(driver, name, section_xpaths) is None:
                continue
            if find_nominee(driver, nominee_xpath, nominee_name) is None:
                continue
            if not vote_xpath:
                continue

            attempted += 1
            try:
                voted = cast_vote(
                    driver,
                    nominee_name,
                    vote_xpath,
                    account if fill_details else None,
                )
            except VoteTimeLock as tlock:
                log(f"[{account['id']}] Vote time-lock: {tlock.message!r}")
                log(
                    f"[{account['id']}] Locked until "
                    f"{tlock.wait_until:%Y-%m-%d %H:%M:%S}."
                )
                record_time_lock(
                    state, account, successes, tlock.wait_until, tlock.message
                )
                time_locked = True
                break

            if not voted:
                log(f"[{account['id']}] Skipping pause for {name}.")
                continue
            successes.append((name, nominee_name))
            time.sleep(2)

        if successes and not time_locked:
            record_account_run(state, account, successes)

    except TimeoutException as error:
        log(f"[{account['id']}] Timed out: {error}")
    except WebDriverException as error:
        log(f"[{account['id']}] Browser error: {error}")
    except KeyboardInterrupt:
        log(f"[{account['id']}] Stopped by user.")
        raise
    finally:
        if driver is not None:
            if pause:
                try:
                    input(f"[{account['id']}] Press Enter to close the browser...")
                except (EOFError, KeyboardInterrupt):
                    pass
            try:
                driver.quit()
                log(f"[{account['id']}] Browser closed.")
            except WebDriverException as error:
                log(f"[{account['id']}] Error closing browser: {error}")

    log(
        f"[{account['id']}] Run complete: {len(successes)}/{attempted} votes "
        f"accepted{'; time-locked' if time_locked else ''}."
    )
    return successes, attempted, time_locked

def run_pass(accounts, state, force=False, pause=False):
    """Vote every due account once. Returns (attempted, succeeded, time_locked)."""
    due_accounts = [a for a in accounts if account_due(state, a, force=force)[0]]

    if not due_accounts:
        return 0, 0, []

    log(
        f"Processing {len(due_accounts)} due account(s): "
        f"{[a['id'] for a in due_accounts]}"
    )

    attempted = 0
    succeeded = 0
    time_locked = []
    for account in due_accounts:
        successes, att, tl = vote_account(account, state, pause=pause)
        attempted += att
        succeeded += len(successes)
        if tl:
            time_locked.append(account["id"])
    return attempted, succeeded, time_locked


def _load_accounts_or_retry(account_filter, poll):
    """Load accounts, or return None after sleeping if not available."""
    try:
        accounts = load_details()
    except (FileNotFoundError, ValueError) as error:
        log(f"Could not load details.txt: {error}. Retrying in {poll}s.")
        return None

    if account_filter:
        accounts = [a for a in accounts if a["id"] == account_filter]
        if not accounts:
            log(f"Account {account_filter!r} not found in details.txt. Retrying in {poll}s.")
            return None

    return accounts


def run_once(accounts, force=False, pause=False):
    """One-shot mode: single pass, then exit."""
    state = load_state()
    attempted, succeeded, time_locked = run_pass(
        accounts, state, force=force, pause=pause
    )
    log(
        f"Done. Votes: {succeeded}/{attempted}; "
        f"time-locked: {time_locked or 'none'}."
    )
    if attempted and not succeeded and not time_locked:
        return 1
    return 0


def run_forever(force=False, pause=False, account_filter=None, poll=DEFAULT_POLL_SECONDS):
    """Daemon loop: process due accounts, sleep until the next is due."""
    log("SESSION STARTED. Press Ctrl+C to stop.")

    force_next_pass = force
    last_logged_target = None
    first_iteration = True

    while True:
        accounts = _load_accounts_or_retry(account_filter, poll)
        if accounts is None:
            try:
                time.sleep(poll)
            except KeyboardInterrupt:
                log("Stopped by user.")
                return 130
            continue

        state = load_state()

        if first_iteration:
            log(f"Loaded {len(accounts)} account(s):")
            for account in accounts:
                due, reason = account_due(state, account, force=False)
                log(f"  [{account['id']}] {reason}")
            first_iteration = False

        attempted, succeeded, time_locked = run_pass(
            accounts, state, force=force_next_pass, pause=pause
        )
        if attempted:
            log(
                f"Pass complete: {succeeded}/{attempted} votes; "
                f"time-locked: {time_locked or 'none'}."
            )
        force_next_pass = False  # --force only applies to the first pass

        # Decide how long to sleep before the next check.
        sleep_seconds, next_due = compute_next_wake(
            state, accounts, max_sleep=poll
        )
        if sleep_seconds <= 0:
            # Something is still due after the pass (e.g. transient failure
            # without a time-lock). Enforce a cooldown to avoid tight loop.
            sleep_seconds = MIN_COOLDOWN_SECONDS

        if next_due is not None:
            target_str = next_due.strftime("%Y-%m-%d %H:%M")
            if target_str != last_logged_target:
                log(
                    f"Next due at {next_due:%Y-%m-%d %H:%M:%S} "
                    f"({_format_delta((next_due - _now()).total_seconds())} from now). "
                    f"Sleeping up to {_format_delta(sleep_seconds)} per poll."
                )
                last_logged_target = target_str
        else:
            last_logged_target = None

        try:
            time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            log("Stopped by user.")
            return 130


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Mombasa Business Awards voter (multi-account, daemon)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single pass and exit (old behaviour). Default is daemon mode.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore each account's schedule gate. In daemon mode, applies only to the first pass.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print per-account schedule state and exit (no browser launched).",
    )
    parser.add_argument(
        "--account",
        default=None,
        help="Only process this record ID (e.g. TEST_RECORD_1).",
    )
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Prompt before closing each account's browser (debugging).",
    )
    parser.add_argument(
        "--poll",
        type=int,
        default=DEFAULT_POLL_SECONDS,
        help=f"Poll interval in seconds while idle (default {DEFAULT_POLL_SECONDS}).",
    )
    args = parser.parse_args(argv)

    # ---- status mode ----
    if args.status:
        state = load_state()
        try:
            accounts = load_details()
        except (FileNotFoundError, ValueError) as error:
            log(f"Could not load details.txt: {error}")
            return 4
        if args.account:
            accounts = [a for a in accounts if a["id"] == args.account]
            if not accounts:
                log(f"Account {args.account!r} not found.")
                return 3

        payload = {
            "state_path": str(STATE_PATH),
            "profile_root": str(PROFILE_ROOT),
            "accounts": {},
        }
        for account in accounts:
            due, reason = account_due(state, account, force=False)
            entry = state.get("accounts", {}).get(account["id"], {})
            history = entry.get("history") if isinstance(entry, dict) else None
            payload["accounts"][account["id"]] = {
                "email": account["Email"],
                "due": due,
                "reason": reason,
                "last_vote_at": entry.get("last_vote_at") if isinstance(entry, dict) else None,
                "interval_seconds": entry.get("interval_seconds") if isinstance(entry, dict) else None,
                "next_vote_at": entry.get("next_vote_at") if isinstance(entry, dict) else None,
                "time_lock_message": entry.get("time_lock_message") if isinstance(entry, dict) else None,
                "time_lock_at": entry.get("time_lock_at") if isinstance(entry, dict) else None,
                "history_count": len(history) if isinstance(history, list) else 0,
            }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    # ---- load accounts once for the initial validation ----
    try:
        accounts = load_details()
    except (FileNotFoundError, ValueError) as error:
        log(f"Could not load details.txt: {error}")
        return 4

    if args.account:
        accounts = [a for a in accounts if a["id"] == args.account]
        if not accounts:
            log(f"Account {args.account!r} not found in details.txt.")
            return 3

    # ---- one-shot or daemon ----
    if args.once:
        return run_once(accounts, force=args.force, pause=args.pause)
    return run_forever(
        force=args.force,
        pause=args.pause,
        account_filter=args.account,
        poll=args.poll,
    )


if __name__ == "__main__":
    raise SystemExit(main())