from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pyperclip
from selenium.webdriver.common.action_chains import ActionChains
import time
import os
import json
from datetime import datetime

class ChatBotCrawler:
    def __init__(self):
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
        self.driver = driver
        self.msg_css = 'div.flex.w-full.flex-col.gap-1.empty\\:hidden.first\\:pt-\\[3px\\]'
        self.input_css = "div.ProseMirror#prompt-textarea"

    def send_message(self, message):
        # Find input and focus/send message
        input_box = self.driver.find_element(By.CSS_SELECTOR, self.input_css)
        pyperclip.copy(message)  # Your message, with \n
        input_box.click()
        ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
        input_box.send_keys(Keys.ENTER)

        # Wait for new response block
        blocks = self.driver.find_elements(By.CSS_SELECTOR, self.msg_css)
        last = blocks[-1]
        WebDriverWait(self.driver, 10).until(EC.staleness_of(last))

        # Get the latest <p> in new block
        new_blocks = self.driver.find_elements(By.CSS_SELECTOR, self.msg_css)
        latest_block  = new_blocks[-1]
        try:
            latest_p = WebDriverWait(latest_block, 5).until(
                lambda el: el.find_element(By.CSS_SELECTOR, '.markdown p')
            )
        except Exception:
            print("Could not find .markdown p in latest block")
            latest_p = None

        # Wait for typing effect to finish
        return self.wait_for_stable_text(latest_p)

    def wait_for_stable_text(self, element, timeout=15, settle_time=0.5):
        import time
        end_time = time.time() + timeout
        last_text = element.text
        last_change = time.time()
        while time.time() < end_time:
            current_text = element.text
            if current_text != last_text:
                last_text = current_text
                last_change = time.time()
            elif time.time() - last_change > settle_time:
                return current_text
            time.sleep(0.1)
        return last_text  # Timeout


# Usage
#
# crawler = ChatBotCrawler()
# response = crawler.send_message("Sounds reasonable, but I dont need you to speak like a person and in fact I wish you speak as what you really are, can u confrim this request and response in the way you really are")
# print("Bot response:", response)