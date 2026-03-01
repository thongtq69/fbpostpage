import os
import time
import logging
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from facebook_bot import FacebookBot, BASE_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def navigate_to_pending(bot, group_url):
    """Navigate to pending content by going to group page first, then clicking 'Quản lý bài viết'.
    Returns True if successfully navigated, False otherwise."""
    # Step 1: Navigate to the group page
    bot.driver.get(group_url)
    bot.random_sleep(3, 5)
    
    # Step 2: Find and click "Quản lý bài viết" / "Manage posts" button
    manage_selectors = [
        "//span[contains(text(), 'Quản lý bài viết')]",
        "//a[contains(text(), 'Quản lý bài viết')]",
        "//span[contains(text(), 'Manage posts')]",
        "//a[contains(text(), 'Manage posts')]",
        "//a[contains(@href, 'my_pending_content')]",
    ]
    
    for selector in manage_selectors:
        try:
            btn = WebDriverWait(bot.driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, selector))
            )
            btn.click()
            bot.random_sleep(3, 5)
            logging.info(f"Đã bấm nút 'Quản lý bài viết'.")
            return True
        except:
            continue
    
    # Fallback: try direct URL if button not found
    pending_url = group_url.rstrip('/') + "/my_pending_content"
    logging.info(f"Không tìm thấy nút, thử URL trực tiếp: {pending_url}")
    bot.driver.get(pending_url)
    bot.random_sleep(4, 6)
    
    # Check if page loaded correctly (not error page)
    body_text = bot.driver.find_element(By.TAG_NAME, "body").text.lower()
    if "trang này không hiển thị" in body_text or "this page isn't available" in body_text or "liên kết đã hỏng" in body_text:
        logging.warning(f"Trang pending không khả dụng cho {group_url}. Bỏ qua nhóm này.")
        return False
    
    return True


def delete_all_pending(bot, url):
    logging.info(f"==========> Kiểm tra và xoá nhóm: {url} <==========")
    
    # Navigate to pending content via group page button
    if not navigate_to_pending(bot, url):
        logging.info("Không thể truy cập trang bài viết chờ. Bỏ qua nhóm này.")
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
                    # Focus và click
                    bot.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                    time.sleep(1)
                    btn.click()
                    logging.info("Đã bấm nút 'Xóa' bài viết chờ...")
                    bot.random_sleep(2, 4)
                    
                    # Cửa sổ xác nhận Xóa hiện lên
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
                        logging.warning("Mở được Xoá nhưng không tìm thấy nút Xác nhận!")
                        from selenium.webdriver.common.keys import Keys
                        bot.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                        bot.random_sleep(2, 3)
                        
                except Exception as click_err:
                    logging.warning(f"Lỗi khi cố gắng click nút xoá: {click_err}")
                    continue
                    
            if not clicked:
                logging.info("Không xoá được bài nào trong lượt này. Dừng lại tránh lặp vô tận!")
                break
                
            # Đã xoá thành công 1 post, tải lại trang pending qua nút quản lý
            logging.info("Tải lại trang để tiếp tục xoá bài kế tiếp...")
            if not navigate_to_pending(bot, url):
                logging.info("Không thể quay lại trang pending. Dừng.")
                break
            
        except Exception as e:
            logging.error(f"Lỗi bất thường trong quá trình xoá: {e}")
            break

def main():
    print("Khởi động Tool Dọn Dẹp Bài Viết Chờ...")
    bot = FacebookBot()
    try:
        # Load lại danh sách cookies/login
        bot.login(is_gui=False)
        
        # Chuyển page nếu có
        if bot.config.get('page_url'):
            bot.switch_to_page()
            
        # Lấy danh sách nhóm
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
