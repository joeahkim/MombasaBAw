from datetime import datetime, timedelta
import argparse
import json
import os
import random
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

from details import load_details  # the second script, save as details.py


URL = "https://mombasabusinessawards.kenyachamber.co.ke/vote/"

# Each entry:
#   (section name, section xpaths, nominee xpath, nominee name,
#    vote button xpath, fill_details)
# fill_details=True  -> fill email/phone from details.txt before submitting
# fill_details=False -> submit only; the page has stored the form details
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
VOTE_FORM_ERROR_XPATH = '//*[@id="vote-form"]/div[2]/div[2]/div'
VOTE_FORM_DISMISS_XPATH = '//*[@id="vote-form"]/div[1]/button'

# How long to wait for the vote form to auto-close after submit before assuming failure.
VOTE_FORM_DISAPPEAR_TIMEOUT = 10
# How long to wait for the specific error div to appear after that.
VOTE_FORM_ERROR_TIMEOUT = 5

# Fallback XPaths checked for error text inside the form if the specific error div is empty/absent.
ERROR_TEXT_XPATHS = (
    '//*[@id="vote-form"]//*[contains(@class, "error")]',
    '//*[@id="vote-form"]//*[contains(@class, "invalid")]',
    '//*[@id="vote-form"]//*[@role="alert"]',
    '//*[@id="vote-error"]',
    '//*[@id="vote-form"]//*[contains(@class, "message")]',
)

# ---------------------------------------------------------------------------
# Session + schedule persistence
# ---------------------------------------------------------------------------

# Where the last-vote time and next-vote time are stored between runs.
STATE_PATH = Path(__file__).with_name("vote_state.json")

# Persistent Chrome profile so the site's stored form details / cookies /
# localStorage survive between runs. This is what makes "the page stores the
# form details" work across separate launches of this script.
USER_DATA_DIR = Path(__file__).with_name("chrome_profile")

# Required gap between votes: random in [2h03m, 2h15m].
MIN_INTERVAL_SECONDS = 2 * 3600 + 3 * 60    # 7,380 s
MAX_INTERVAL_SECONDS = 2 * 3600 + 15 * 60   # 8,100 s

# Keep only the most recent N history entries in the state file.
HISTORY_LIMIT = 20


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


def load_state():
    """Return the persisted state dict, or {} if missing/unreadable."""
    if not STATE_PATH.exists():
        return {}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        log(f"Could not read state file {STATE_PATH}: {error}. Starting fresh.")
        return {}
    if not isinstance(data, dict):
        log(f"State file {STATE_PATH} is not a JSON object. Starting fresh.")
        return {}
    return data


def save_state(state):
    """Atomically write the state dict to STATE_PATH."""
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = STATE_PATH.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp_path, STATE_PATH)
    except OSError as error:
        log(f"Could not write state file {STATE_PATH}: {error}")


def pick_interval_seconds():
    """Random vote interval in [2h03m, 2h15m]."""
    return random.randint(MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS)


def record_vote(state, section, nominee):
    """Append a successful vote to the state and schedule the next one."""
    now = _now()
    entry = {
        "at": now.isoformat(timespec="seconds"),
        "section": section,
        "nominee": nominee,
    }
    history = state.setdefault("history", [])
    if not isinstance(history, list):
        history = []
        state["history"] = history
    history.append(entry)
    del history[:-HISTORY_LIMIT]

    interval = pick_interval_seconds()
    state["last_vote_at"] = entry["at"]
    state["last_vote_section"] = section
    state["last_vote_nominee"] = nominee
    state["interval_seconds"] = interval
    state["next_vote_at"] = (now + timedelta(seconds=interval)).isoformat(timespec="seconds")
    save_state(state)
    log(
        f"Recorded vote for {nominee} ({section}); "
        f"next allowed at {state['next_vote_at']} (+{_format_delta(interval)})."
    )


def check_schedule(state, force=False):
    """Return True if a vote is allowed now, else log why and return False."""
    next_dt = _parse_dt(state.get("next_vote_at"))
    if next_dt is None:
        return True

    remaining = (next_dt - _now()).total_seconds()
    if remaining <= 0:
        return True

    if force:
        log(
            f"Schedule says next vote at {next_dt:%Y-%m-%d %H:%M:%S} "
            f"({_format_delta(remaining)} from now) — overriding with --force."
        )
        return True

    log(
        f"Not due yet. Last vote at {state.get('last_vote_at', '?')}, "
        f"next at {next_dt:%Y-%m-%d %H:%M:%S} ({_format_delta(remaining)} from now). "
        f"Use --force to override."
    )
    return False


# ---------------------------------------------------------------------------
# Browser / page helpers
# ---------------------------------------------------------------------------


def build_driver():
    """Launch Chrome with a persistent profile so session/form state survives."""
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument("--profile-directory=Default")
    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options,
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
    """Return any visible error text inside the vote form, or ''."""
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


def cast_vote(driver, nominee_name, vote_button_xpath, details=None):
    """Click Vote, optionally fill email/phone, submit, confirm form closes.

    If ``details`` is provided, the email/phone fields are filled from it
    (the CEO of The Year flow). If ``details`` is None, the fields are left
    as-is because the page has already stored them from the previous vote,
    and only Submit is clicked.

    On success (form disappears on its own) returns True.
    On failure (form still visible after submit) logs the error from
    //*[@id="vote-form"]/div[2]/div[2]/div, clicks the dismiss button at
    //*[@id="vote-form"]/div[1]/button, and returns False.
    """
    # 1) Click the nominee's Vote button.
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

    # 2) Wait for the vote form and the submit button.
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

    # 3) Fill email/phone only when details were supplied (CEO of The Year).
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

    # 4) Submit.
    try:
        submit_button.click()
        log("Clicked submit.")
    except (NoSuchElementException, WebDriverException) as error:
        log(f"Submit click failed: {error}")
        return False

    # 5) Happy path: wait for the form to close on its own.
    try:
        WebDriverWait(driver, VOTE_FORM_DISAPPEAR_TIMEOUT).until(
            EC.invisibility_of_element_located((By.XPATH, VOTE_FORM_XPATH))
        )
        log(f"Vote form closed for {nominee_name} — vote accepted.")
        return True
    except TimeoutException:
        log(f"Vote form still visible after submit for {nominee_name} — checking for error.")

    # 6) Error path: the form didn't close. Inspect the specific error div.
    error_text = ""
    try:
        error_div = WebDriverWait(driver, VOTE_FORM_ERROR_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, VOTE_FORM_ERROR_XPATH))
        )
        error_text = " ".join(
            (error_div.get_attribute("textContent") or error_div.text)
            .replace("\xa0", " ")
            .split()
        )
    except TimeoutException:
        # Fall back to generic probes so we still log *something*.
        error_text = _collect_error_text(driver)

    if error_text:
        log(f"Vote error for {nominee_name}: {error_text!r}")
    else:
        log(f"Vote form still visible for {nominee_name} but no error text found.")

    # 7) Dismiss the form so the page is usable for the next section.
    try:
        dismiss_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, VOTE_FORM_DISMISS_XPATH))
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", dismiss_button
        )
        dismiss_button.click()
        log("Clicked dismiss button on the vote form.")
        # Best-effort confirmation the form actually closed.
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mombasa Business Awards voter")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore the 2h03m–2h15m schedule gate and vote now.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print the stored schedule/state and exit.",
    )
    args = parser.parse_args(argv)

    state = load_state()

    if args.status:
        if not state:
            print(json.dumps({"status": "no state file yet", "path": str(STATE_PATH)}, indent=2))
            return 0
        next_dt = _parse_dt(state.get("next_vote_at"))
        payload = dict(state)
        payload["state_path"] = str(STATE_PATH)
        payload["user_data_dir"] = str(USER_DATA_DIR)
        if next_dt is not None:
            remaining = (next_dt - _now()).total_seconds()
            payload["seconds_until_next_vote"] = int(max(0, remaining))
            payload["next_vote_due"] = remaining <= 0
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if not check_schedule(state, force=args.force):
        return 2

    details = load_details()  # raises on invalid/missing details.txt
    log(f"Loaded details for record {details['id']!r}.")
    log(f"State file: {STATE_PATH}")
    log(f"Chrome profile: {USER_DATA_DIR}")

    driver = None
    attempted = 0
    succeeded = 0
    try:
        driver = build_driver()
        driver.maximize_window()
        log(f"Opening {URL}")
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
            voted = cast_vote(
                driver,
                nominee_name,
                vote_xpath,
                details if fill_details else None,
            )
            if not voted:
                # Change this to `break` if you want to stop on first failure.
                log(f"Skipping pause for {name}; moving to next section.")
                continue
            succeeded += 1
            record_vote(state, name, nominee_name)
            time.sleep(2)  # brief pause before next section, per spec

    except TimeoutException as error:
        log(f"Timed out while waiting for the page to load: {error}")
    except WebDriverException as error:
        log(f"Browser or page error: {error}")
    except KeyboardInterrupt:
        log("Stopped by user.")
    finally:
        if driver is not None:
            try:
                input("Press Enter to close the browser...")
            except (EOFError, KeyboardInterrupt):
                pass
            driver.quit()
            log("Browser closed.")

    log(f"Run complete: {succeeded}/{attempted} votes accepted.")
    if attempted and not succeeded:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())