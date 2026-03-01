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
    """Navigate to pending content by going to group page first, then clicking 'Quản lý bài viết'."""
    bot.driver.get(group_url)
    bot.random_sleep(3, 5)
    
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
    
    pending_url = group_url.rstrip('/') + "/my_pending_content"
    logging.info(f"Không tìm thấy nút, thử URL trực tiếp: {pending_url}")
    bot.driver.get(pending_url)
    bot.random_sleep(4, 6)
    
    body_text = bot.driver.find_element(By.TAG_NAME, "body").text.lower()
    if "trang này không hiển thị" in body_text or "this page isn't available" in body_text or "liên kết đã hỏng" in body_text:
        logging.warning(f"Trang pending không khả dụng cho {group_url}. Bỏ qua nhóm này.")
        return False
    
    return True


def js_click(driver, element):
    """Click using JavaScript to bypass elements blocking the click."""
    driver.execute_script("arguments[0].click();", element)


def find_delete_buttons(bot):
    """Tìm tất cả nút Xóa hiển thị trên trang."""
    xpath_delete = "//div[@aria-label='Xóa' or @aria-label='Xoá' or @aria-label='Delete'][@role='button']"
    buttons = bot.driver.find_elements(By.XPATH, xpath_delete)
    
    if not buttons:
        xpath_delete_text = "//div[@role='button' and (contains(., 'Xóa') or contains(., 'Xoá') or contains(., 'Delete'))]"
        buttons = bot.driver.find_elements(By.XPATH, xpath_delete_text)
    
    return [b for b in buttons if b.is_displayed()]


def delete_all_pending(bot, url):
    logging.info(f"==========> Kiểm tra và xoá nhóm: {url} <==========")
    
    if not navigate_to_pending(bot, url):
        logging.info("Không thể truy cập trang bài viết chờ. Bỏ qua nhóm này.")
        return
    
    # Kiểm tra trạng thái rỗng trước
    body_text = bot.driver.find_element(By.TAG_NAME, "body").text.lower()
    if "không có bài" in body_text or "nothing to show" in body_text or "no posts to show" in body_text or "no pending posts" in body_text:
        logging.info(f"Đã DỌN SẠCH (hoặc không có) bài viết chờ trong nhóm này.")
        return
    
    # Tìm tất cả nút Xóa trên trang
    delete_btns = find_delete_buttons(bot)
    
    if not delete_btns:
        logging.info("Không tìm thấy nút Xoá nào. Chuyển nhóm...")
        return
    
    total = len(delete_btns)
    deleted = 0
    logging.info(f"Tìm thấy {total} nút Xóa. Tiến hành xóa liên tục...")
    
    # Xóa tất cả bài viết liên tục KHÔNG tải lại trang
    for i in range(total):
        try:
            # Tìm lại nút sau mỗi lần xóa vì DOM có thể thay đổi
            current_btns = find_delete_buttons(bot)
            if not current_btns:
                logging.info("Hết nút Xóa trên trang.")
                break
            
            btn = current_btns[0]  # Luôn lấy nút đầu tiên còn lại
            
            # Cuộn vào giữa màn hình
            bot.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", btn
            )
            time.sleep(0.5)
            
            # Click nút Xóa
            js_click(bot.driver, btn)
            bot.random_sleep(1, 2)
            
            # Tìm và bấm nút Xác nhận trong hộp thoại
            xpath_confirm = "//div[@role='dialog']//div[@role='button' and (contains(., 'Xóa') or contains(., 'Xoá') or contains(., 'Delete') or contains(., 'Confirm') or contains(., 'Xác nhận'))]"
            
            try:
                confirm_btn = WebDriverWait(bot.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath_confirm))
                )
                js_click(bot.driver, confirm_btn)
                deleted += 1
                logging.info(f"Đã xóa bài {deleted}/{total}")
                bot.random_sleep(2, 3)  # Đợi Facebook xử lý xóa
            except:
                logging.warning("Không tìm thấy nút Xác nhận. Đóng dialog và thử bài tiếp theo...")
                from selenium.webdriver.common.keys import Keys
                bot.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                bot.random_sleep(1, 2)
                
        except Exception as click_err:
            logging.warning(f"Lỗi khi xóa bài thứ {i+1}: {click_err}")
            continue
    
    logging.info(f"Hoàn tất! Đã xóa {deleted} bài viết chờ trong nhóm này.")


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
