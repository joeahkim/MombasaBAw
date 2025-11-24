from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import time

driver = webdriver.Chrome()
driver.get("https://mombasabusinessawards.kenyachamber.co.ke/vote/")

time.sleep(3)

# Best Start Up Business - Intrasoft Technologies Limited
option_label = driver.find_element(
    By.XPATH, "//label[contains(., 'Intrasoft Technologies Limited')]"
)
driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", option_label)
time.sleep(1.5)

option_label.click()
time.sleep(1)

vote_button = driver.find_element(By.CSS_SELECTOR, "input.ays_finish_poll[value='Vote']")

driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", vote_button)
time.sleep(5)
vote_button.click()
print("Voted BEST START UP BUSINESS as Intrasoft Technologies Limited successfully!")
# Best Start Up Business - Intrasoft Technologies Limited done
time.sleep(5)
# Best Start Up Business - Hazina Group Foundation
option_label = driver.find_element(
    By.XPATH, "//label[contains(., 'Hazina Group Foundation')]"
)
driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", option_label)
time.sleep(5)

option_label.click()
time.sleep(5)

vote_button = driver.find_element(By.CSS_SELECTOR, "input.ays_finish_poll[value='Vote']")

driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", vote_button)
time.sleep(5)
vote_button.click()
print("Voted MOST INNOVATIVE BUSINESS as Hazina Group Foundation successfully!")
# Best Start Up Business - Hazina Group Foundation done
time.sleep(5)
# Best Innovation Hub - Intrasoft Tech and Innovation Hub
option_label = driver.find_element(
    By.XPATH, "//label[contains(., 'Intrasoft Tech and Innovation Hub')]"
)
driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", option_label)
time.sleep(5)

option_label.click()
time.sleep(5)

vote_button = driver.find_element(By.CSS_SELECTOR, "input.ays_finish_poll[value='Vote']")

driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", vote_button)
time.sleep(5)
vote_button.click()
print("Voted BEST INNOVATION HUB as Intrasoft Tech and Innovation Hub successfully!")
# Best Innovation Hub - Intrasoft Tech and Innovation Hub done
time.sleep(5)
# Best Use of Technology - Intrasoft Technologies Limited
option_label = driver.find_element(
    By.XPATH, "//label[contains(., 'Intrasoft Technologies Limited')]"
)
driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", option_label)
time.sleep(5)

option_label.click()
time.sleep(5)

vote_button = driver.find_element(By.CSS_SELECTOR, "input.ays_finish_poll[value='Vote']")

driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", vote_button)
time.sleep(5)
vote_button.click()
print("Voted BEST USE OF TECHNOLOGY as Intrasoft Technologies Limited successfully!")
# Best Use of Technology - Intrasoft Technologies Limited done
time.sleep(5)
# Best Training Institution - Intrasoft Tech and Innovation Hub
option_label = driver.find_element(
    By.XPATH, "//label[contains(., 'Intrasoft Tech and Innovation Hub')]"
)
driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", option_label)
time.sleep(5)

option_label.click()
time.sleep(5)

vote_button = driver.find_element(By.CSS_SELECTOR, "input.ays_finish_poll[value='Vote']")

driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", vote_button)
time.sleep(5)
vote_button.click()
print("Voted Intrasoft Tech and Innovation Hub as BEST TRAINING INSTITUTION successfully!")
# Best Training Institution - Intrasoft Tech and Innovation Hub done
time.sleep(5)

# Best Business Development Service Provider - Hazina Group Foundation
option_label = driver.find_element(
    By.XPATH, "//label[contains(., 'Hazina Group Foundation')]"
)
driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", option_label)
time.sleep(5)

option_label.click()
time.sleep(5)

vote_button = driver.find_element(By.CSS_SELECTOR, "input.ays_finish_poll[value='Vote']")

driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", vote_button)
time.sleep(5)
vote_button.click()
print("Voted Hazina Group Foundation as BEST BUSINESS DEVELOPMENT SERVICE PROVIDER successfully!")
# Best Business Development Service Provider - Hazina Group Foundation done
time.sleep(5)

# Best Microfinance Institution - Hazina Group Foundation
option_label = driver.find_element(
    By.XPATH, "//label[contains(., 'Hazina Group Foundation')]"
)
driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", option_label)
time.sleep(5)

option_label.click()
time.sleep(5)

vote_button = driver.find_element(By.CSS_SELECTOR, "input.ays_finish_poll[value='Vote']")

driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", vote_button)
time.sleep(5)
vote_button.click()
print("Voted Hazina Group Foundation as BEST BEST MICROFINANCE successfully!")
# Best Microfinance Institution - Hazina Group Foundation done
time.sleep(5)


driver.quit()
