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
            
            # Sau khi bấm, nếu gặp lỗi "Trang này hiện không hiển thị" thì bấm Tải lại
            try:
                body_now = bot.driver.find_element(By.TAG_NAME, "body").text.lower()
                if "trang này hiện không hiển thị" in body_now or "trang này không hiển thị" in body_now:
                    reload_btn_xpath = "//div[@role='button' and contains(., 'Tải lại trang')]"
                    r_btn = WebDriverWait(bot.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, reload_btn_xpath))
                    )
                    r_btn.click()
                    logging.info("Gặp trang lỗi kỹ thuật, đã bấm 'Tải lại trang'.")
                    bot.random_sleep(5, 7)
            except:
                pass

            logging.info(f"Đã bấm nút 'Quản lý bài viết'.")
            return True
        except:
            continue
    
    pending_url = group_url.rstrip('/') + "/my_pending_content"
    logging.info(f"Không tìm thấy nút, thử URL trực tiếp: {pending_url}")
    bot.driver.get(pending_url)
    bot.random_sleep(4, 6)
    
    # Kiểm tra lỗi ở đây nữa nếu đi bằng URL trực tiếp
    try:
        body_now = bot.driver.find_element(By.TAG_NAME, "body").text.lower()
        if "trang này hiện không hiển thị" in body_now or "trang này không hiển thị" in body_now:
            reload_btn_xpath = "//div[@role='button' and contains(., 'Tải lại trang')]"
            r_btns = bot.driver.find_elements(By.XPATH, reload_btn_xpath)
            if r_btns:
                r_btns[0].click()
                logging.info("Gặp trang lỗi kỹ thuật (URL), đã bấm 'Tải lại trang'.")
                bot.random_sleep(5, 7)
    except:
        pass
    
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
    
def delete_all_pending(bot, url):
    logging.info(f"==========> Kiểm tra và xoá nhóm: {url} <==========")
    
    if not navigate_to_pending(bot, url):
        logging.info("Không thể truy cập trang bài viết chờ. Bỏ qua nhóm này.")
        return
    
    deleted = 0
    consecutive_empty_checks = 0
    max_empty_checks = 3 # Thử scroll vài lần trước khi thực sự bỏ cuộc
    
    while True:
        try:
            # 1. Kiểm tra trạng thái rỗng
            body_text = bot.driver.find_element(By.TAG_NAME, "body").text.lower()
            if "không có bài" in body_text or "nothing to show" in body_text or "no posts to show" in body_text or "no pending posts" in body_text:
                logging.info(f"Đã DỌN SẠCH (hoặc không có) bài viết chờ trong nhóm này.")
                break
                
            # 2. Lấy danh sách nút Xoá hiện có
            delete_btns = find_delete_buttons(bot)
            
            if not delete_btns:
                # Nếu không thấy nút, thử scroll xuống xem có bài mới load lên không
                logging.info("Chưa thấy nút Xoá, đang scroll xuống...")
                bot.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                bot.random_sleep(3, 5)
                consecutive_empty_checks += 1
                
                if consecutive_empty_checks >= max_empty_checks:
                    logging.info("Đã scroll nhiều lần vẫn không thấy bài mới. Chuyển nhóm...")
                    break
                continue
            
            # Reset check khi thấy có bài
            consecutive_empty_checks = 0
            
            # 3. Tiến hành xoá bài đầu tiên nhìn thấy
            btn = delete_btns[0]
            try:
                # Cuộn vào giữa màn hình
                bot.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", btn
                )
                time.sleep(1)
                
                # Click nút Xóa
                js_click(bot.driver, btn)
                bot.random_sleep(1, 2)
                
                # Tìm và bấm nút Xác nhận trong hộp thoại (Dialog)
                xpath_confirm = "//div[@role='dialog']//div[@role='button' and (contains(., 'Xóa') or contains(., 'Xoá') or contains(., 'Delete') or contains(., 'Confirm') or contains(., 'Xác nhận'))]"
                
                try:
                    # Chờ hộp thoại confirm hiện lên
                    confirm_btn = WebDriverWait(bot.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, xpath_confirm))
                    )
                    js_click(bot.driver, confirm_btn)
                    deleted += 1
                    logging.info(f"Đã xoá bài thứ {deleted}...")
                    
                    # Đợi bài biến mất khỏi danh sách (Fade out)
                    bot.random_sleep(3, 4) 
                except:
                    # Nếu lỗi dialog, thử bấm ESC để đóng và tiếp tục
                    logging.warning("Không thấy nút Xác nhận xoá, đang đóng dialog...")
                    from selenium.webdriver.common.keys import Keys
                    bot.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                    bot.random_sleep(1, 2)
            
            except Exception as e:
                logging.warning(f"Lỗi khi xử lý 1 article: {e}")
                # Nếu rủi ro kẹt bài này, scroll qua nó hoặc reload nhẹ
                bot.driver.execute_script("window.scrollBy(0, 300);")
                bot.random_sleep(1, 2)

        except Exception as e:
            logging.error(f"Lỗi vòng lặp xoá: {e}")
            break
            
    logging.info(f"Hoàn tất nhóm! Tổng cộng đã xoá {deleted} bài bài viết chờ.")


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
