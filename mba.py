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

from details import load_details  # the second script, save as load_details.py


URL = "https://mombasabusinessawards.kenyachamber.co.ke/vote/"

# Each entry: (section name, section xpaths, nominee xpath, nominee name, vote button xpath or None)
SECTIONS = (
    (
        "CEO of The Year",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[2]/div/h3',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[2]/div/ul/li[14]',
        "Intrasoft Technologies",
        '//*[@id="scroll"]/section[2]/div/div[3]/div[2]/div/ul/li[14]/button',
    ),
    (
        "Most Innovative Business",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[3]/div/h3',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[3]/div/ul/li[13]',
        "Intrasoft Technologies",
        None,
    ),
    (
        "Best in Corporate Social Responsibility",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[15]/div/h3',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[15]/div/ul/li[4]',
        "Hazina Group Foundation",
        None,
    ),
    (
        "Best SME",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[20]/div/h3',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[20]/div/ul/li[15]',
        "INTRASOFT TECHNOLOGIES LIMITED",
        None,
    ),
    (
        "Best Innovation & Social Impact Hub",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[26]/div/h3',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[26]/div/ul/li[2]',
        "HAZINA GROUP FOUNDATION",
        None,
    ),
    (
        "Most Inclusive Enterprise",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[35]/div/h3',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[35]/div/ul/li[3]',
        "HAZINA GROUP FOUNDATION",
        None,
    ),
)

VOTE_EMAIL_XPATH = '//*[@id="vote-email"]'
VOTE_PHONE_XPATH = '//*[@id="vote-phone"]'
VOTE_SUBMIT_XPATH = '//*[@id="vote-submit"]'


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


def cast_vote(driver, nominee_name, vote_button_xpath, details):
    """Click Vote, fill email + phone, submit. Returns True on success."""
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
        email_field = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, VOTE_EMAIL_XPATH))
        )
        phone_field = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, VOTE_PHONE_XPATH))
        )
        submit_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, VOTE_SUBMIT_XPATH))
        )
    except TimeoutException:
        log("Vote form (email/phone/submit) did not appear.")
        return False

    email_field.clear()
    email_field.send_keys(details["Email"])
    phone_field.clear()
    phone_field.send_keys(details["Phone"])
    log(f"Filled email={details['Email']!r}, phone={details['Phone']!r}.")

    try:
        submit_button.click()
        log("Clicked submit.")
    except (NoSuchElementException, WebDriverException) as error:
        log(f"Submit click failed: {error}")
        return False

    return True


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

        for name, section_xpaths, nominee_xpath, nominee_name, vote_xpath in SECTIONS:
            if find_section(driver, name, section_xpaths) is None:
                continue
            if find_nominee(driver, nominee_xpath, nominee_name) is None:
                continue
            if vote_xpath:
                cast_vote(driver, nominee_name, vote_xpath, details)
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