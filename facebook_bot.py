import json
import time
import random
import os
import sys
import logging
import ssl

# Fix SSL Certificate Error on macOS
ssl._create_default_https_context = ssl._create_unverified_context

# --- PATCH FOR PYTHON 3.12+ (Missing distutils) ---
if sys.version_info >= (3, 12):
    import types
    # Ensure distutils and distutils.version exist in sys.modules
    if 'distutils' not in sys.modules:
        sys.modules['distutils'] = types.ModuleType('distutils')
    if 'distutils.version' not in sys.modules:
        sys.modules['distutils.version'] = types.ModuleType('distutils.version')
    
    # Mock LooseVersion if it doesn't exist
    if not hasattr(sys.modules['distutils.version'], 'LooseVersion'):
        class LooseVersion:
            def __init__(self, vstring):
                self.vstring = str(vstring)
                # Simple parsing of version string to a list of integers
                self.version = []
                for component in self.vstring.split('.'):
                    if component.isdigit():
                        self.version.append(int(component))
                    else:
                        # Handle non-numeric parts if necessary, or just ignore/store as is
                        # For chrome versions, it's usually all numeric.
                        pass
                        
            def __eq__(self, other):
                if isinstance(other, LooseVersion):
                    return self.version == other.version
                return NotImplemented

            def __lt__(self, other):
                if isinstance(other, LooseVersion):
                    return self.version < other.version
                return NotImplemented

            def __le__(self, other):
                if isinstance(other, LooseVersion):
                    return self.version <= other.version
                return NotImplemented

            def __gt__(self, other):
                if isinstance(other, LooseVersion):
                    return self.version > other.version
                return NotImplemented

            def __ge__(self, other):
                if isinstance(other, LooseVersion):
                    return self.version >= other.version
                return NotImplemented
                
            def __str__(self):
                return self.vstring
                
            def __repr__(self):
                return f"LooseVersion('{self.vstring}')"
        
        sys.modules['distutils.version'].LooseVersion = LooseVersion
# --------------------------------------------------

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# Logging setup
logging.basicConfig(
    filename='facebook_bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class FacebookBot:
    def __init__(self, config_path='config.json'):
        self.load_config(config_path)
        self.setup_driver()

    def load_config(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logging.info("Config loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            raise

    def setup_driver(self):
        options = uc.ChromeOptions()
        options.add_argument("--disable-notifications")
        # Add random user agent if needed, but UC handles it well usually
        
        try:
            self.driver = uc.Chrome(options=options, use_subprocess=True)
            self.driver.maximize_window()
            logging.info("Driver initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize driver: {e}")
            raise

    def random_sleep(self, min_time=None, max_time=None):
        if min_time is None:
            min_time = self.config.get('min_delay', 1)
        if max_time is None:
            max_time = self.config.get('max_delay', 3)
        time.sleep(random.uniform(min_time, max_time))

    def human_typing(self, element, text):
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))

    def load_cookies_from_file(self, cookie_path='cookies.json'):
        if not os.path.exists(cookie_path):
            logging.info("No cookies file found at " + cookie_path)
            return False
            
        try:
            with open(cookie_path, 'r') as f:
                cookies = json.load(f)
            
            logging.info(f"Found {len(cookies)} cookies.")
            for cookie in cookies:
                # Sanitize cookie fields for Selenium
                if 'sameSite' in cookie:
                    if cookie['sameSite'] not in ["Strict", "Lax", "None"]:
                        del cookie['sameSite']
                
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    # Ignore specific cookie errors, usually domain mismatches or invalid fields
                    pass
            
            logging.info("Cookies loaded successfully.")
            return True
        except Exception as e:
            logging.error(f"Error loading cookies: {e}")
            return False

    def login(self):
        logging.info("Starting login process...")
        self.driver.get("https://www.facebook.com")
        self.random_sleep(2, 4)

        # Try to load cookies
        if self.load_cookies_from_file():
            logging.info("Refreshing page to apply cookies...")
            self.driver.refresh()
            self.random_sleep(3, 5)

        try:
            # Check if already logged in (look for search bar or generic logged-in element)
            try:
                self.driver.find_element(By.CSS_SELECTOR, "input[type='search']")
                logging.info("Already logged in.")
                return
            except:
                pass

            email_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            self.human_typing(email_input, self.config['email'])
            self.random_sleep()

            pass_input = self.driver.find_element(By.ID, "pass")
            self.human_typing(pass_input, self.config['password'])
            self.random_sleep()

            login_btn = self.driver.find_element(By.NAME, "login")
            login_btn.click()
            
            # Wait for navigation or potential 2FA
            self.random_sleep(5, 7)
            
            # Check for 2FA
            if "checkpoint" in self.driver.current_url or "two_step_verification" in self.driver.page_source:
                logging.warning("2FA detected. Please enter code manually in browser.")
                input("2FA detected. Press Enter here after you have verified and are on the homepage...")
            
            logging.info("Login successful.")

        except Exception as e:
            logging.error(f"Error during login: {e}")
            self.driver.save_screenshot("login_error.png")
            raise

    def navigate_to_group(self):
        logging.info(f"Navigating to group: {self.config['group_url']}")
        self.driver.get(self.config['group_url'])
        self.random_sleep(3, 5)
        
        # Scroll down a bit to load content
        for _ in range(3):
            self.driver.execute_script("window.scrollBy(0, 500);")
            self.random_sleep(1, 2)
        
        # Scroll back up
        self.driver.execute_script("window.scrollTo(0, 0);")
        self.random_sleep()

    def create_post(self):
        logging.info("Attempting to create post...")
        try:
            # Click "Write something..." or "Create Post"
            # Attempt multiple selectors
            create_post_selectors = [
                 "//span[contains(text(), 'Bạn đang nghĩ gì?')]",
                 "//span[contains(text(), 'Write something...')]",
                 "//div[@role='button']//span[contains(text(), 'Tạo bài viết công khai')]",
                 "//div[@role='button']//span[contains(text(), 'Create a public post')]",
                 "//span[contains(text(), 'Bạn viết gì đi...')]",
                 "//span[contains(text(), 'Bạn đang bán gì?')]",
                 "//span[contains(text(), 'What are you selling?')]",
                 "//div[@aria-label='Tạo bài viết']",
                 "//div[@aria-label='Create post']",
                 "//div[@aria-label='Write something...']",
                 "//div[@aria-label='Bạn đang nghĩ gì?']"
            ]
            
            post_box_opened = False
            for selector in create_post_selectors:
                try:
                    # Short wait for each to speed up if not found
                    element = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    element.click()
                    post_box_opened = True
                    logging.info(f"Clicked post button using selector: {selector}")
                    break
                except:
                    continue
            
            if not post_box_opened:
                # Fallback: clicking the generic input area based on class names common in FB
                 try:
                    # Try finding the first div with role=button in the feed area
                    fallback_xpath = "(//div[@role='feed']//div[@role='button'])[1]" 
                    element = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, fallback_xpath))
                    )
                    element.click()
                    logging.info("Clicked post button using fallback selector.")
                 except Exception as e:
                     logging.error("Could not find post button via selectors or fallback.")
                     raise e

            self.random_sleep(2, 4)

            # Check if we triggered a "Buy/Sell" wizard or standard post
            # Sometimes simpler is better: interacting with the active element or looking for the text input
            
            # Input Text
            # Content editable dive
            active_element = self.driver.switch_to.active_element
            if self.config.get('post_content'):
                 self.human_typing(active_element, self.config['post_content'])
            
            self.random_sleep()

            # Upload Images
            if self.config.get('image_paths'):
                self.upload_images()

            self.random_sleep(2, 4)
            
            # Click Post
            post_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@aria-label='Đăng' or @aria-label='Post']"))
            )
            post_btn.click()
            
            logging.info("Post button clicked. Waiting for confirmation...")
            self.random_sleep(5, 7)
            # Check for success (e.g., post box closed, "Just now" text appeared, etc.) - simple wait for now
            logging.info("Finished posting.")

        except Exception as e:
            logging.error(f"Error creating post: {e}")
            self.driver.save_screenshot("post_error.png")
            raise

    def upload_images(self):
        # This is tricky because the input[type=file] is often hidden
        # Common pattern: find the input type=file
        try:
            file_input = self.driver.find_element(By.XPATH, "//input[@type='file' and @multiple]")
            
            paths = "\n".join([os.path.abspath(p) for p in self.config['image_paths']])
            file_input.send_keys(paths)
            logging.info("Images uploaded.")
            self.random_sleep(3, 5) # Wait for upload
        except Exception as e:
            logging.error(f"Failed to upload images: {e}")

    def run(self):
        try:
            self.login()
            if self.config.get('group_url'):
                self.navigate_to_group()
                self.create_post()
            else:
                 logging.warning("No group URL provided in config.")
        except Exception as e:
            logging.error(f"Bot execution failed: {e}")
        finally:
            logging.info("Closing driver...")
            self.driver.quit()

if __name__ == "__main__":
    bot = FacebookBot()
    bot.run()
