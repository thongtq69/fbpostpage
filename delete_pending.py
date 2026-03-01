import os
import time
import logging
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from facebook_bot import FacebookBot, BASE_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def navigate_to_pending_page(bot, group_url):
    """Navigate to the pending content page via 3-dot menu → 'Nội dung của bạn'.
    Falls back to direct URL if menu approach fails.
    Returns True if successfully on pending page."""
    
    # Use the shared method from FacebookBot
    navigated = bot._navigate_to_pending_via_menu(group_url)
    
    if navigated:
        # Click on 'Đang chờ' tab if visible
        try:
            pending_tab_selectors = [
                "//span[text()='Đang chờ']",
                "//span[text()='Pending']",
                "//a[contains(@href,'pending')]",
            ]
            for sel in pending_tab_selectors:
                tabs = bot.driver.find_elements(By.XPATH, sel)
                for tab in tabs:
                    if tab.is_displayed():
                        tab.click()
                        bot.random_sleep(3, 4)
                        return True
        except:
            pass
        return True
    
    # Fallback: direct URL
    pending_url = group_url.rstrip('/') + "/my_pending_content"
    logging.info(f"Falling back to direct URL: {pending_url}")
    bot.driver.get(pending_url)
    bot.random_sleep(4, 6)
    
    # Check if blocked
    body_text = bot.driver.find_element(By.TAG_NAME, "body").text.lower()
    if "tạm thời bị chặn" in body_text or "temporarily blocked" in body_text:
        logging.warning("Bị Facebook chặn tạm thời! Chuyển sang nhóm tiếp theo...")
        return False
    
    return True

def delete_all_pending(bot, url):
    logging.info(f"==========> Kiểm tra và xoá nhóm: {url} <==========")
    
    # Navigate to pending page via menu
    if not navigate_to_pending_page(bot, url):
        logging.warning("Không thể truy cập trang bài viết chờ. Bỏ qua nhóm này.")
        return
    
    while True:
        try:
            # Kiểm tra trạng thái rỗng
            body_text = bot.driver.find_element(By.TAG_NAME, "body").text.lower()
            if "không có bài" in body_text or "nothing to show" in body_text or "no posts to show" in body_text or "no pending posts" in body_text:
                logging.info(f"Đã DỌN SẠCH (hoặc không có) bài viết chờ trong nhóm này.")
                break
            
            # Nếu còn bài, tiến hành tìm nút Xóa / Delete
            xpath_delete = "//div[@role='button' and (contains(., 'Xóa') or contains(., 'Xoá') or contains(., 'Delete'))]"
            delete_buttons = bot.driver.find_elements(By.XPATH, xpath_delete)
            
            # Lọc bỏ các phần tử không hiển thị
            valid_btns = [b for b in delete_buttons if b.is_displayed()]
            
            if not valid_btns:
                logging.info("Không tìm thấy thêm nút Xoá nào hiển thị trên màn hình. Chuyển nhóm...")
                break
                
            clicked = False
            for btn in valid_btns:
                try:
                    bot.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                    time.sleep(1)
                    btn.click()
                    logging.info("Đã bấm nút 'Xóa' bài viết chờ...")
                    bot.random_sleep(2, 4)
                    
                    # Tìm nút Xóa/Confirm trong hộp thoại xác nhận
                    xpath_confirm = "//div[@role='dialog']//div[@role='button' and (contains(., 'Xóa') or contains(., 'Xoá') or contains(., 'Delete') or contains(., 'Confirm') or contains(., 'Xác nhận'))]"
                    confirm_buttons = bot.driver.find_elements(By.XPATH, xpath_confirm)
                    
                    confirm_clicked = False
                    for confirm_btn in confirm_buttons:
                        if confirm_btn.is_displayed():
                            confirm_btn.click()
                            logging.info("Đã bấm Xóa ở hộp thoại Xác nhận!")
                            confirm_clicked = True
                            bot.random_sleep(4, 6)
                            break
                            
                    if confirm_clicked:
                        clicked = True
                        break
                    else:
                        logging.warning("Không tìm thấy nút Xác nhận Xóa trong hộp thoại!")
                        bot.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                        bot.random_sleep(2, 3)
                        
                except Exception as click_err:
                    logging.warning(f"Lỗi khi cố gắng click nút xoá: {click_err}")
                    continue
                    
            if not clicked:
                logging.info("Không xoá được bài nào trong lượt này. Dừng lại tránh lặp vô tận!")
                break
                
            # Đã xoá thành công 1 post, navigate lại qua menu để tiếp tục
            logging.info("Tải lại trang để tiếp tục xoá bài kế tiếp...")
            if not navigate_to_pending_page(bot, url):
                logging.warning("Không thể tải lại trang bài viết chờ. Dừng xoá.")
                break
            
        except Exception as e:
            logging.error(f"Lỗi bất thường trong quá trình xoá: {e}")
            break

def main():
    print("Khởi động Tool Dọn Dẹp Bài Viết Chờ...")
    bot = FacebookBot()
    try:
        bot.login(is_gui=False)
        
        if bot.config.get('page_url'):
            bot.switch_to_page()
            
        groups = bot.config.get('group_urls', [])
        if not groups and bot.config.get('group_url'):
            groups = [bot.config['group_url']]
            
        if not groups:
            logging.error("Không tìm thấy danh sách nhóm nào trong cấu hình!")
            return
            
        for url in groups:
            delete_all_pending(bot, url)
            
        logging.info("==========> ĐÃ DỌN DẸP HOÀN TẤT TẤT CẢ CÁC NHÓM <==========")
        
    except Exception as e:
        logging.error(f"Lỗi: {e}")
    finally:
        logging.info("Đang đóng trình duyệt...")
        try:
            bot.driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()
