import re
import time
from datetime import datetime

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ================== CẤU HÌNH ==================

BASE_URL = "https://www.evn.com.vn/vi-VN/news-l/Thong-tin-tom-tat-van-hanh-HTD-Quoc-gia-60-2015"
TOTAL_PAGES = 76   # theo bạn nói

# ================== HÀM HỖ TRỢ ==================

def extract_number_vi(s: str):
    """'39.989,9' -> 39989.9"""
    if s is None:
        return None
    s = s.strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

def extract_date_from_title(title: str):
    """
    'Thông tin chung về vận hành hệ thống điện Quốc gia ngày 23/11/2025'
      -> 2025-11-23
    """
    m = re.search(r"ngày\s+(\d{1,2}/\d{1,2}/\d{4})", title)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%d/%m/%Y").date()
    except Exception:
        return None

def extract_peak_from_text(text: str):
    """
    Tìm 'Công suất lớn nhất trong ngày: 39989,9 MW' trong nội dung.
    Có fallback cho 'phụ tải cực đại ... MW'.
    """
    # mẫu chuẩn bạn đưa
    pat1 = re.compile(
        r"Công\s*suất\s*lớn\s*nhất\s*trong\s*ngày\s*:\s*([\d\.,]+)\s*MW",
        re.IGNORECASE
    )
    m1 = pat1.search(text)
    if m1:
        return extract_number_vi(m1.group(1))

    # fallback rộng hơn
    pat2 = re.compile(
        r"(phụ\s*tải|công\s*suất).*?(cực\s*đại|lớn\s*nhất).*?([\d\.,]+)\s*MW",
        re.IGNORECASE
    )
    m2 = pat2.search(text)
    if m2:
        return extract_number_vi(m2.group(3))

    return None

def init_driver():
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless=new")  # nếu muốn chạy ẩn
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.maximize_window()
    return driver

# ================== CÀO DỮ LIỆU ==================

def crawl_evn_peak():
    driver = init_driver()
    wait = WebDriverWait(driver, 20)
    results = []

    try:
        for page in range(1, TOTAL_PAGES + 1):
            list_url = f"{BASE_URL}?page={page}"
            print(f"\n=== ĐANG CÀO TRANG {page}/{TOTAL_PAGES}: {list_url} ===")
            driver.get(list_url)
            time.sleep(2)

            # lấy tất cả link bài trên trang đó
            links = driver.find_elements(By.CSS_SELECTOR, "a")
            article_links = []

            for a in links:
                href = a.get_attribute("href")
                title = a.text.strip()
                if not href or not title:
                    continue

                # đúng pattern bạn mô tả
                if "Thong-tin-chung-ve-van-hanh-he-thong-dien-Quoc-gia-ngay" in href:
                    article_links.append((title, href))

            # remove trùng
            seen = set()
            uniq_articles = []
            for title, href in article_links:
                if href not in seen:
                    seen.add(href)
                    uniq_articles.append((title, href))

            print(f"  -> Tìm được {len(uniq_articles)} bài trong trang {page}")

            # vào từng bài
            for title, href in uniq_articles:
                print(f"    [BÀI] {title} -> {href}")
                driver.get(href)

                try:
                    detail_div = wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "div.chitiettinbai")
                        )
                    )
                except Exception as e:
                    print("      -> Không tìm thấy div.chitiettinbai:", e)
                    continue

                text = detail_div.text

                date_val = extract_date_from_title(title)
                peak_mw = extract_peak_from_text(text)

                if not date_val:
                    print("      -> Không đọc được ngày từ title, bỏ qua.")
                    continue
                if peak_mw is None:
                    print("      -> Không đọc được 'Công suất lớn nhất trong ngày', bỏ qua.")
                    continue

                results.append(
                    {
                        "date": date_val.isoformat(),
                        "peak_MW": peak_mw,
                        "title": title,
                        "url": href,
                    }
                )

                time.sleep(0.5)

    finally:
        driver.quit()

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values("date")
        df.to_csv("evn_peak_load_daily_page_param.csv", index=False)
        print("\n✅ ĐÃ LƯU: evn_peak_load_daily_page_param.csv")
        print(df.head())
        print("Tổng số dòng:", len(df))
    else:
        print("\n❌ Không thu được dữ liệu – cần kiểm tra lại.")

if __name__ == "__main__":
    crawl_evn_peak()
