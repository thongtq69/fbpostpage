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

# Get the directory of the current script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Logging setup
logging.basicConfig(
    filename=os.path.join(BASE_DIR, 'facebook_bot.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class FacebookBot:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(BASE_DIR, 'config.json')
        self.load_config(config_path)
        self.setup_driver()

    def load_config(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            # Auto-load images from 'pic' folder
            pic_folder = os.path.join(BASE_DIR, 'pic')
            if os.path.isdir(pic_folder):
                valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
                for filename in os.listdir(pic_folder):
                    if filename.lower().endswith(valid_extensions):
                        full_path = os.path.join(pic_folder, filename)
                        if 'image_paths' not in self.config:
                            self.config['image_paths'] = []
                        # Avoid duplicates if multiple runs or if manually added
                        if full_path not in self.config['image_paths']:
                            self.config['image_paths'].append(full_path)
                logging.info(f"Loaded {len(self.config.get('image_paths', []))} images from config and 'pic' folder.")

            logging.info("Config loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            raise

    def get_chrome_version(self):
        try:
            import subprocess
            cmd = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--version']
            output = subprocess.check_output(cmd).decode('utf-8')
            # Extract major version, e.g., "Google Chrome 145.0.7632.117" -> 145
            version = int(output.split()[-1].split('.')[0])
            return version
        except Exception as e:
            logging.warning(f"Could not detect Chrome version: {e}")
            return None

    def setup_driver(self):
        options = uc.ChromeOptions()
        options.add_argument("--disable-notifications")
        
        chrome_version = self.get_chrome_version()
        if chrome_version:
            logging.info(f"Detected Chrome version: {chrome_version}")
        
        try:
            # Pass version_main to ensure the driver matches the browser
            self.driver = uc.Chrome(options=options, use_subprocess=True, version_main=chrome_version)
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
        text = str(text)
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))

    def load_cookies_from_file(self, cookie_path=None):
        if cookie_path is None:
            cookie_path = os.path.join(BASE_DIR, 'cookies.json')
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

    def save_cookies_to_file(self, cookie_path=None):
        if cookie_path is None:
            cookie_path = os.path.join(BASE_DIR, 'cookies.json')
        try:
            cookies = self.driver.get_cookies()
            with open(cookie_path, 'w') as f:
                json.dump(cookies, f)
            logging.info(f"Saved {len(cookies)} cookies to {cookie_path}")
        except Exception as e:
            logging.error(f"Error saving cookies: {e}")

    def login(self, is_gui=False):
        logging.info("Starting login process...")
        self.driver.get("https://www.facebook.com")
        self.random_sleep(2, 4)

        # Handle Cookie Banners if they appear
        cookie_banners = [
            "//button[@data-cookiebanner='accept_button']",
            "//button[contains(text(), 'Allow all cookies')]",
            "//button[contains(text(), 'Cho phép tất cả cookie')]",
            "//div[@aria-label='Cho phép tất cả cookie']",
            "//div[@aria-label='Allow all cookies']"
        ]
        for selector in cookie_banners:
            try:
                btn = self.driver.find_element(By.XPATH, selector)
                btn.click()
                logging.info(f"Accepted cookies using: {selector}")
                self.random_sleep(1, 2)
                break
            except:
                continue

        # Try to load cookies from file
        if self.load_cookies_from_file():
            logging.info("Refreshing page to apply cookies...")
            self.driver.refresh()
            self.random_sleep(3, 5)

        try:
            # Improved check for "Already Logged In"
            logged_in_indicators = [
                "input[type='search']",
                "[aria-label='Facebook']",
                "[role='navigation']",
                "a[href='/home.php']",
                "[aria-label*='Trang chủ']",
                "[aria-label*='Home']"
            ]
            
            for indicator in logged_in_indicators:
                try:
                    if self.driver.find_elements(By.CSS_SELECTOR, indicator):
                        logging.info(f"Already logged in (detected via {indicator}).")
                        return
                except:
                    continue

            # If not logged in, look for email/pass fields
            email_selectors = [
                 (By.ID, "email"),
                 (By.NAME, "email"),
                 (By.CSS_SELECTOR, "input[name='email']"),
                 (By.CSS_SELECTOR, "input[placeholder*='Email']")
            ]
            
            email_input = None
            for by, selector in email_selectors:
                try:
                    email_input = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    if email_input:
                        break
                except:
                    continue
            
            if not email_input:
                logging.error("Could not find email input field.")
                self.driver.save_screenshot(os.path.join(BASE_DIR, "login_error_email.png"))
                raise Exception("Email field not found")

            self.human_typing(email_input, self.config['email'])
            self.random_sleep(1, 2)

            # Pass field
            pass_selectors = [
                (By.ID, "pass"),
                (By.NAME, "pass"),
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.CSS_SELECTOR, "input[name='pass']")
            ]
            
            pass_input = None
            for by, selector in pass_selectors:
                try:
                    pass_input = self.driver.find_element(by, selector)
                    if pass_input:
                        break
                except:
                    continue
            
            if not pass_input:
                logging.error("Could not find password field.")
                raise Exception("Password field not found")

            self.human_typing(pass_input, self.config['password'])
            self.random_sleep(1, 2)

            # Login Button
            login_selectors = [
                (By.NAME, "login"),
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.CSS_SELECTOR, "[role='button'][name='login']"),
                (By.XPATH, "//button[contains(text(), 'Log In')]"),
                (By.XPATH, "//button[contains(text(), 'Đăng nhập')]")
            ]
            
            login_clicked = False
            for by, selector in login_selectors:
                try:
                    btn = self.driver.find_element(by, selector)
                    if btn.is_displayed():
                        btn.click()
                        login_clicked = True
                        logging.info(f"Clicked login button using {selector}")
                        break
                except:
                    continue
            
            if not login_clicked:
                logging.warning("Login button not found or not clickable, trying to press ENTER...")
                pass_input.send_keys(Keys.ENTER)
            
            # Wait for navigation or potential 2FA
            self.random_sleep(5, 7)
            
            # Check for 2FA or Checkpoints
            current_url = self.driver.current_url
            if "checkpoint" in current_url or "two_step_verification" in self.driver.page_source:
                logging.warning("2FA/Checkpoint detected.")
                if is_gui:
                    logging.info("GUI Mode: Waiting 60s for manual verification...")
                    # In GUI mode, we just wait a long time for the user to do it
                    time.sleep(60)
                else:
                    print("\n" + "!" * 60)
                    print("PHÁT HIỆN XÁC THỰC 2 LỚP (2FA) HOẶC KIỂM TRA BẢO MẬT.")
                    print("Vui lòng thực hiện xác minh trên trình duyệt Chrome đang mở.")
                    print("Sau khi xác minh xong và vào được trang chủ Facebook, hãy quay lại đây.")
                    input(">>> Nhấn phím ENTER tại đây để tiếp tục các bước post bài...")
                    print("!" * 60 + "\n")
            
            # Save cookies after successful login/verification
            self.save_cookies_to_file()
            logging.info("Login process completed.")

        except Exception as e:
            logging.error(f"Error during login: {e}")
            self.driver.save_screenshot(os.path.join(BASE_DIR, "login_error.png"))
            raise


    def navigate_to_group(self, group_url=None):
        if not group_url:
            group_url = self.config.get('group_url')
        
        if not group_url:
            logging.error("No group URL provided.")
            return False

        logging.info(f"Navigating to group: {group_url}")
        try:
            self.driver.get(group_url)
            self.random_sleep(3, 5)
            
            # Scroll down a bit to load content
            for _ in range(3):
                self.driver.execute_script("window.scrollBy(0, 500);")
                self.random_sleep(1, 2)
            
            # Scroll back up
            self.driver.execute_script("window.scrollTo(0, 0);")
            self.random_sleep(1, 2)
            return True
        except Exception as e:
            logging.error(f"Navigation failed to {group_url}: {e}")
            return False

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

    def switch_to_page(self):
        page_url = self.config.get('page_url')
        if not page_url:
            logging.info("No page_url provided, skipping switch.")
            return

        logging.info(f"Navigating to page to switch profile: {page_url}")
        self.driver.get(page_url)
        self.random_sleep(3, 5)

        # Look for "Switch now" or "Chuyển ngay" button
        # Button often has aria-label or text
        switch_selectors = [
            "//div[@aria-label='Chuyển ngay']",
            "//span[contains(text(), 'Chuyển ngay')]",
            "//div[@aria-label='Switch now']",
            "//span[contains(text(), 'Switch now')]",
             # Fallback to menu interactions if needed (omitted for simplicity unless requested)
        ]

        switched = False
        for selector in switch_selectors:
            try:
                btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                btn.click()
                switched = True
                logging.info("Clicked 'Switch now' button.")
                self.random_sleep(5, 8) # Wait for reload
                break
            except:
                continue
        
        if not switched:
            logging.warning("Could not find 'Switch now' button. Assuming already on correct profile or button hidden.")

    def run(self, is_gui=False):
        try:
            self.login(is_gui=is_gui)
            if self.config.get('page_url'):
                self.switch_to_page()
                
            # Support both single string and list for groups
            groups = self.config.get('group_urls', [])
            if not groups and self.config.get('group_url'):
                groups = [self.config['group_url']]

            if not groups:
                logging.warning("No group URLs provided in config.")
                return

            logging.info(f"Starting post cycle for {len(groups)} groups.")
            
            for i, url in enumerate(groups):
                try:
                    if self.navigate_to_group(url):
                        self.create_post()
                        
                        # Only wait if not the last group in this cycle
                        if i < len(groups) - 1:
                            delay_min = self.config.get('between_groups_min', 60)
                            delay_max = self.config.get('between_groups_max', 180)
                            logging.info(f"Waiting {delay_min}-{delay_max}s before next group...")
                            self.random_sleep(delay_min, delay_max)
                    else:
                        logging.warning(f"Skipping post for {url} due to navigation failure.")
                except Exception as group_err:
                    logging.error(f"Failed to post to {url}: {group_err}")
                    self.driver.save_screenshot(os.path.join(BASE_DIR, f"post_error_{i}.png"))
                    
            logging.info("Completed post cycle for all groups.")
            
        except Exception as e:
            logging.error(f"Bot execution failed: {e}")
            raise
        finally:
            logging.info("Closing driver...")
            try:
                self.driver.quit()
            except:
                pass

if __name__ == "__main__":
    bot = FacebookBot()
    bot.run()
