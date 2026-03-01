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
import re

# Suppress OSError during Chrome.__del__ on Windows
try:
    original_del = uc.Chrome.__del__
    def safe_del(self):
        try:
            original_del(self)
        except OSError:
            pass
        except Exception:
            pass
    uc.Chrome.__del__ = safe_del
except Exception:
    pass
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
        self.current_post_index = self.load_state()
        self.is_active = True

    def load_config(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(BASE_DIR, 'config.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            # Auto-load images from 'pic' folder if empty
            if not self.config.get('image_paths'):
                pic_dir = os.path.join(BASE_DIR, 'pic')
                if os.path.exists(pic_dir):
                    valid_exts = ('.jpg', '.jpeg', '.png', '.gif')
                    self.config['image_paths'] = [
                        os.path.join(pic_dir, f) for f in os.listdir(pic_dir)
                        if f.lower().endswith(valid_exts)
                    ]
                    logging.info(f"Loaded {len(self.config['image_paths'])} images from config and 'pic' folder.")
            logging.info("Config loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            raise

    def load_state(self):
        state_file = os.path.join(BASE_DIR, 'bot_state.json')
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    return json.load(f).get('current_index', 0)
            except:
                pass
        return 0

    def save_state(self, index):
        state_file = os.path.join(BASE_DIR, 'bot_state.json')
        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump({'current_index': index}, f)
        except Exception as e:
            logging.warning(f"Failed to save state: {e}")

    def get_chrome_version(self):
        try:
            import subprocess
            import platform
            if platform.system() == "Windows":
                cmd = ['reg', 'query', 'HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon', '/v', 'version']
                output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('utf-8')
                version = int(output.strip().split()[-1].split('.')[0])
                return version
            else:
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
        # Tăng tốc độ bằng cách nhập theo cụm (chunk) ngẫu nhiên thay vì từng ký tự một
        i = 0
        while i < len(text):
            chunk_size = random.randint(4, 10)
            element.send_keys(text[i:i+chunk_size])
            time.sleep(random.uniform(0.01, 0.03))
            i += chunk_size

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


    def navigate_to_pending_via_button(self, group_url):
        """Navigate to pending content by going to group page first, then clicking 'Quản lý bài viết'.
        Returns True if successfully navigated to pending content page, False otherwise."""
        # Step 1: Navigate to the group page
        self.driver.get(group_url)
        self.random_sleep(3, 5)
        
        for selector in manage_selectors:
            try:
                btn = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                btn.click()
                self.random_sleep(3, 5)
                
                # Sau khi bấm, nếu gặp lỗi "Trang này hiện không hiển thị" thì bấm Tải lại
                try:
                    body_now = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                    if "trang này hiện không hiển thị" in body_now or "trang này không hiển thị" in body_now:
                        reload_btn_xpath = "//div[@role='button' and contains(., 'Tải lại trang')]"
                        r_btn = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, reload_btn_xpath))
                        )
                        r_btn.click()
                        logging.info("Gặp trang lỗi kỹ thuật, đã bấm 'Tải lại trang'.")
                        self.random_sleep(5, 7)
                except:
                    pass

                logging.info(f"Clicked 'Quản lý bài viết' button.")
                return True
            except:
                continue
        
        # Fallback: try direct URL if button not found (some groups may not show it)
        pending_url = group_url.rstrip('/') + "/my_pending_content"
        logging.info(f"Button not found, trying direct URL: {pending_url}")
        self.driver.get(pending_url)
        self.random_sleep(4, 6)
        
        # Kiểm tra lỗi ở đây nữa nếu đi bằng URL trực tiếp
        try:
            body_now = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            if "trang này hiện không hiển thị" in body_now or "trang này không hiển thị" in body_now:
                reload_btn_xpath = "//div[@role='button' and contains(., 'Tải lại trang')]"
                r_btns = self.driver.find_elements(By.XPATH, reload_btn_xpath)
                if r_btns:
                    r_btns[0].click()
                    logging.info("Gặp trang lỗi kỹ thuật (URL), đã bấm 'Tải lại trang'.")
                    self.random_sleep(5, 7)
        except:
            pass
        
        # Check if page loaded correctly (not error page)
        body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
        if "trang này không hiển thị" in body_text or "this page isn't available" in body_text or "liên kết đã hỏng" in body_text:
            logging.warning(f"Pending content page not available for {group_url}. Proceeding to post.")
            return False
        
        return True

    def check_pending_posts(self, group_url):
        if not group_url:
            return False
            
        logging.info(f"Checking pending posts for: {group_url}")
        
        try:
            # Navigate to pending content via group page button
            if not self.navigate_to_pending_via_button(group_url):
                return False
            
            # Verify we didn't get redirected to the main page
            current = self.driver.current_url
            if "my_pending_content" not in current and "pending" not in current:
                logging.info("Not on pending content page. Proceeding to post.")
                return False
            
            # Detect by checking text content
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            
            # 1. Check if explicit "empty" message is displayed
            if "không có bài" in body_text or "không có bài viết nào để hiển thị" in body_text or "nothing to show here" in body_text or "no posts to show" in body_text or "no pending posts" in body_text:
                logging.info("Explicit 'no pending posts' message found. Proceeding to post.")
                return False
                
            # 2. Check for actual post elements (articles)
            articles = self.driver.find_elements(By.CSS_SELECTOR, "div[role='article']")
            if len(articles) > 0:
                logging.info(f"Found {len(articles)} pending post articles. Skipping group.")
                return True
                
            # 3. Check if the header shows a count like "đang chờ · 2" using regex
            if re.search(r'(đang chờ|pending( posts)?)\s*\n*\s*·\s*\d+', body_text):
                logging.info("Detected pending posts by header count regex. Skipping group.")
                return True
                
            # 4. Fallback check for action buttons typical of pending posts
            if ("chỉnh sửa" in body_text and "xóa" in body_text) or ("edit" in body_text and "delete" in body_text):
                if "đang chờ" in body_text or "pending" in body_text:
                    logging.info("Detected pending post action buttons (Edit/Delete). Skipping group.")
                    return True
                    
            # If none of the above, default to safe assumption: no pending
            logging.info("No definitive pending posts found. Proceeding to post.")
            return False
            
        except Exception as e:
            logging.error(f"Error checking pending posts: {e}")
            return False

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
                 "//span[contains(text(), 'Viết nội dung gì đó')]",
                 "//span[contains(text(), 'Viết gì đó')]",
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

            self.random_sleep(3, 5)

            # Wait explicitly for the popup's textbox to be ready and interactable
            # Some groups open a 'Buy/Sell' popup, others 'Discussion'. 
            # Searching for the contenteditable textbox is usually safer than just assuming the active element.
            textbox = None
            try:
                # Tìm element text box chính (thường là cái rộng trãi nhất và có aria-label liên quan đến tạo bài)
                textbox_xpath = "//div[@role='textbox' and @contenteditable='true']"
                textboxes = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, textbox_xpath))
                )
                
                # Nếu có nhiều textbox (VD trong form Bán hàng có Tiêu đề và Mô tả), 
                # thường cái cuối cùng hoặc cái có aria-label là chỗ thích hợp nhất để viết (Mô tả).
                textbox = textboxes[-1] 
                
                try:
                    textbox.click()
                except:
                    self.driver.execute_script("arguments[0].focus();", textbox)
                self.random_sleep(1, 2)
            except Exception as wait_err:
                logging.warning(f"Did not find explicit textbox to click: {wait_err}")

            if self.config.get('post_content'):
                try:
                    # Type trực tiếp vào textbox nếu tìm thấy thẻ an toàn
                    if textbox:
                        self.human_typing(textbox, self.config['post_content'])
                    else:
                        # Fallback cuối cùng mới dùng active element
                        active_element = self.driver.switch_to.active_element
                        self.human_typing(active_element, self.config['post_content'])
                except Exception as type_err:
                    logging.error(f"Failed to type content: {type_err}")
            
            self.random_sleep()

            # Upload Images
            if self.config.get('image_paths'):
                self.upload_images()

            self.random_sleep(2, 4)
            
            # Click Post
            for _ in range(3):
                try:
                    post_btn = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//div[@aria-label='Đăng' or @aria-label='Post']"))
                    )
                    post_btn.click()
                    break
                except Exception as stale_err:
                    logging.warning(f"Failed to click post, retrying: {stale_err}")
                    self.random_sleep(1, 2)
            else:
                logging.error("Failed to click post button after retries.")
                raise Exception("Could not interact with post button.")
            
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
            # Sometime input file tags are regenerated, we use an explicit wait
            file_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='file' and @multiple]"))
            )
            paths = "\n".join([os.path.abspath(p) for p in self.config['image_paths']])
            file_input.send_keys(paths)
            logging.info("Images uploaded.")
            self.random_sleep(4, 6) # Wait for upload preview
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

    def run(self, is_gui=False, continuous=True):
        try:
            self.login(is_gui=is_gui)
            if getattr(self, "is_active", True) and self.config.get('page_url'):
                self.switch_to_page()
                
            while getattr(self, "is_active", True):
                # Reload config dynamicly for each cycle
                try:
                    self.load_config()
                except Exception as e:
                    logging.warning(f"Could not reload config: {e}")
                    
                groups = self.config.get('group_urls', [])
                if not groups and self.config.get('group_url'):
                    groups = [self.config['group_url']]

                if not groups:
                    logging.warning("No group URLs provided in config.")
                    break

                start_idx = self.load_state()
                if start_idx >= len(groups):
                    start_idx = 0
                    
                logging.info(f"Starting post cycle for {len(groups)} groups (Resuming from index {start_idx}).")
                
                for i, url in enumerate(groups[start_idx:], start=start_idx):
                    if not getattr(self, "is_active", True):
                        break
                        
                    try:
                        # Check for pending posts before anything else
                        has_pending = self.check_pending_posts(url)
                        
                        if not has_pending:
                            if self.navigate_to_group(url):
                                self.create_post()
                                
                                # Only wait if not the last group in this cycle OR if continuous
                                if i < len(groups) - 1 or continuous:
                                    delay_min = self.config.get('between_groups_min', 60)
                                    delay_max = self.config.get('between_groups_max', 180)
                                    logging.info(f"Waiting {delay_min}-{delay_max}s before next group...")
                                    self.random_sleep(delay_min, delay_max)
                            else:
                                logging.warning(f"Skipping post for {url} due to navigation failure.")
                        else:
                            logging.info(f"Skipped {url} due to existing pending post.")
                            
                        # Save progression index reliably
                        self.save_state(i + 1)
                            
                    except Exception as group_err:
                        logging.error(f"Failed to post to {url}: {group_err}")
                        try:
                            self.driver.save_screenshot(os.path.join(BASE_DIR, f"post_error_{i}.png"))
                        except:
                            pass
                        
                        # Force raise if driver is unrecoverably dead so app.py restarts bot
                        err_str = str(group_err).lower()
                        if "no such window" in err_str or "unreachable" in err_str or "disconnected" in err_str:
                            raise group_err
                        
                if not getattr(self, "is_active", True):
                    break
                    
                # Loop completely finished, reset saved index for the next cycle
                self.save_state(0)
                logging.info("Completed post cycle for all groups.")
                
                if not continuous:
                    break
                    
                # Sleep before cycling all groups again
                rest_min = self.config.get('loop_rest_min', 3600)
                rest_max = self.config.get('loop_rest_max', 7200)
                rest_time = random.randint(rest_min, rest_max)
                logging.info(f"== Cycle completed. Resting {rest_time} seconds before the next loop (Browser stays open)... ==")
                
                import time
                start_rest = time.time()
                while time.time() - start_rest < rest_time:
                    if not getattr(self, "is_active", True):
                        break
                    time.sleep(1)
            
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
    import time
    
    print("Bot is starting in continuous mode. Press Ctrl+C to stop.")
    while True:
        try:
            bot = FacebookBot()
            bot.run(continuous=True)
            # If run completes without exception, it was normally stopped via is_active = False or Ctrl+C
            break
        except KeyboardInterrupt:
            logging.info("Bot stopped by user (Ctrl+C). Exiting.")
            break
        except Exception as main_e:
            logging.error(f"FATAL ERROR! Bot crashed: {main_e}")
            logging.info("Restarting entirely in 30 seconds to recover from crash...")
            time.sleep(30)
