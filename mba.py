from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


URL = "https://mombasabusinessawards.kenyachamber.co.ke/vote/"
SECTION_XPATHS = (
    '//*[@id="scroll"]/section[2]/div/div[3]/div[2]',
    "/html/body/section[2]/div/div[3]/div[2]",
)
NOMINEE_XPATH = '//*[@id="scroll"]/section[2]/div/div[3]/div[2]/div/ul/li[14]'


def log(message):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


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

        section = None
        for xpath in SECTION_XPATHS:
            try:
                section = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                break
            except TimeoutException:
                continue

        if section is None:
            log("CEO of The Year section not found.")
            return

        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", section
        )
        log("CEO of The Year section found.")

        try:
            nominee = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, NOMINEE_XPATH))
            )
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", nominee
            )
            if "Intrasoft Technologies" in nominee.text:
                log("Intrasoft Technologies found.")
            else:
                log("Intrasoft Technologies not found.")
        except TimeoutException:
            log("Intrasoft Technologies not found.")

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
