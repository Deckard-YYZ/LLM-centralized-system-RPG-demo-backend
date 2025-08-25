from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import json
from datetime import datetime

# Set up Selenium WebDriver
chrome_options = Options()
chrome_options.debugger_address = "127.0.0.1:9223"

chrome_service = Service("Z://bussiness//pycharmProjects//9636NetSenProj//chromedriver-win64//chromedriver.exe",
                         log_path="chromedriver.log",
                         verbose=True
                         )
driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
try:
    driver.execute_script("""
        try {
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        } catch(e) {}
    """)
except Exception:
    pass  # Ignore the error

# snapshot count
msg_css = 'div.flex.w-full.flex-col.gap-1.empty\\:hidden.first\\:pt-\\[3px\\]'
initial = len(driver.find_elements(By.CSS_SELECTOR, msg_css))


input_box = driver.find_element(By.CSS_SELECTOR, "div.ProseMirror#prompt-textarea")
# Click to focus, then send
input_box.click()
input_box.send_keys("Wow,asking me instead, that's a sharp turn. I see you are a bit defensive, right?", Keys.ENTER)  # Or just Keys.SHIFT+ENTER if that's how the site sends



blocks = driver.find_elements(By.CSS_SELECTOR, msg_css)
last = blocks[-1]
# wait until the old last block is detached
WebDriverWait(driver, 10).until(EC.staleness_of(last))


def wait_for_stable_text(element, timeout=15, settle_time=0.5):
    """Wait until element.text is stable for settle_time seconds."""
    end_time = time.time() + timeout
    last_text = element.text
    last_change = time.time()
    while time.time() < end_time:
        current_text = element.text
        if current_text != last_text:
            last_text = current_text
            last_change = time.time()
        elif time.time() - last_change > settle_time:
            return current_text  # text hasn't changed for settle_time
        time.sleep(0.1)
    return last_text  # Timeout, return whatever we have

# now grab the new one
new_blocks = driver.find_elements(By.CSS_SELECTOR, msg_css)
latest_p = new_blocks[-1].find_element(By.CSS_SELECTOR, '.markdown p')

final_text = wait_for_stable_text(latest_p)
print(final_text)

