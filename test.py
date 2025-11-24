from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import *
import time
import random
import random
import datetime

# CONFIGURATION 
URL = "https://mombasabusinessawards.kenyachamber.co.ke/vote/"

VOTES = [
    ("BEST START UP BUSINESS", "Intrasoft Technologies Limited"),
    ("MOST INNOVATIVE BUSINESS", "Hazina Group Foundation"),
    ("BEST INNOVATION HUB", "Intrasoft Tech and Innovation Hub"),
    ("BEST USE OF TECHNOLOGY", "Intrasoft Technologies Limited"),
    ("BEST TRAINING INSTITUTION", "Intrasoft Tech and Innovation Hub"),
    ("BEST BUSINESS DEVELOPMENT SERVICE PROVIDER", "Hazina Group Foundation"),
    ("BEST MICROFINANCE", "Hazina Group Foundation"),
]

def human_delay(min_sec=4, max_sec=6):
    time.sleep(random.uniform(min_sec, max_sec))

def long_break():
    secs = random.randint(5 * 60, 10 * 60)
    mins = secs // 60
    print(f"Taking long break ≈ {mins} minutes ...")
    time.sleep(secs)

options = webdriver.ChromeOptions()
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

# driver = webdriver.Chrome(options=options)
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
driver.maximize_window()
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")

actions = ActionChains(driver)

# FUNCTION TO VOTE IN A CATEGORY
def vote_for(category_name, option_text):
    print(f"[{datetime.datetime.now():%H:%M:%S}] Voting {category_name} → {option_text}")

    try:
        label = driver.find_element(By.XPATH, f"//label[contains(., '{option_text}')]")

        poll_container = label.find_element(By.XPATH, "./ancestor::div[contains(@id, 'ays-poll-id-')]")

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", poll_container)
        human_delay(2, 4)

        actions.move_to_element_with_offset(label, random.randint(-40, 40), random.randint(-15, 15))\
               .pause(random.uniform(0.3, 0.9))\
               .click(label)\
               .perform()
        human_delay(3, 5)

        vote_btn = poll_container.find_element(By.CSS_SELECTOR, "input.ays_finish_poll[value='Vote']")

        driver.execute_script("arguments[0].scrollIntoView({block: 'nearest'});", vote_btn)
        human_delay(1.5, 3.5)

        actions.move_to_element(vote_btn).pause(random.uniform(0.4, 1.2)).click().perform()

        print(f"Successfully voted {category_name}!")
        human_delay(4, 7)

    except Exception as e:
        print(f"ERROR voting {category_name}: {e}")

print("Mombasa Awards Auto-Voter STARTED – runs all day (Ctrl+C to stop)\n")

cycle = 0
while True:
    cycle += 1
    # print("\n" + "="*70)
    print(f"  STARTING CYCLE #{cycle} @ {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    # print("="*70 + "\n")

    try:
        driver.get(URL)
        time.sleep(random.uniform(7, 11))         

        for cat, opt in VOTES:
            vote_for(cat, opt)

        print(f"\nAll {len(VOTES)} votes completed in cycle #{cycle}!\n")
        print("Refreshing page and preparing for next cycle...\n")
        driver.get(URL)
        time.sleep(3)
        long_break()

    except KeyboardInterrupt:
        print("\nStopped by user. Closing browser...")
        break
    except Exception as e:
        print(f"\nUnexpected error: {e}\nRestarting in 5 minutes...")
        time.sleep(300)

driver.quit()
print("Finished. Browser closed.")
