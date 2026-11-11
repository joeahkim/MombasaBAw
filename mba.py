from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


URL = "https://mombasabusinessawards.kenyachamber.co.ke/vote/"
SECTIONS = (
    (
        "CEO of The Year",
        (
            '//*[@id="scroll"]/section[2]/div/div[3]/div[2]',
            "/html/body/section[2]/div/div[3]/div[2]",
        ),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[2]/div/ul/li[14]',
        "Intrasoft Technologies",
    ),
    (
        "Most Innovative Business",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[3]',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[3]/div/ul/li[13]',
        "Intrasoft Technologies",
    ),
    (
        "Best in Corporate Social Responsibility",
        ('//*[@id="scroll"]/section[2]/div/div[3]/div[15]',),
        '//*[@id="scroll"]/section[2]/div/div[3]/div[15]/div/ul/li[4]',
        "Hazina Group Foundation",
    ),
)


def log(message):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


def check_section(driver, name, section_xpaths, nominee_xpath, nominee_name):
    section = None
    for xpath in section_xpaths:
        try:
            section = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            break
        except TimeoutException:
            continue

    if section is None:
        log(f"{name} section not found.")
        return

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", section)
    log(f"{name} section found.")

    try:
        nominee = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, nominee_xpath))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", nominee)
        if nominee_name in nominee.text:
            log(f"{nominee_name} found.")
        else:
            log(f"{nominee_name} not found.")
    except TimeoutException:
        log(f"{nominee_name} not found.")


def main():
    driver = None
    try:
        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install())
        )
        driver.maximize_window()
        log(f"Opening {URL}")
        driver.get(URL)

        wait = WebDriverWait(driver, 20)
        wait.until(
            lambda browser: browser.execute_script("return document.readyState")
            == "complete"
        )

        for name, section_xpaths, nominee_xpath, nominee_name in SECTIONS:
            check_section(driver, name, section_xpaths, nominee_xpath, nominee_name)

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
