from datetime import datetime
import time

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


def log(message):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


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


def main():
    details = load_details()  # raises on invalid/missing details.txt
    log(f"Loaded details for record {details['id']!r}.")

    driver = None
    try:
        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install())
        )
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


if __name__ == "__main__":
    main()