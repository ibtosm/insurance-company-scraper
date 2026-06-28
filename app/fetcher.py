import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

wait: float = 2.0


def create_driver_regular():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    return driver


def create_driver_aflac():
    options = Options()

    # ❌ ヘッドレスはブロックされる
    # options.add_argument("--headless=new")

    # ✔ 普通のブラウザとして振る舞う
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # ✔ User-Agent を偽装
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=options)

    # ✔ navigator.webdriver を False にする
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    return driver


######################################################################


def fetch_html_regular(url: str, driver=None) -> str:
    driver.get(url)

    WebDriverWait(driver, wait).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

    html = driver.page_source
    return html


def fetch_html_Fwdlife(url: str, driver=None) -> str:
    max_page_limit = 3

    driver.get(url)

    # ページングが描画されるまで待つ（最重要）
    WebDriverWait(driver, 10).until(
        lambda d: d.find_elements(
            By.CSS_SELECTOR, "nav[aria-label='pagination navigation'] ul li button"
        )
    )

    html_list = []
    html = driver.page_source
    html_list.append(html)

    soup = BeautifulSoup(html, "html.parser")
    ul = soup.select_one("nav[aria-label='pagination navigation'] ul")

    if not ul:
        print("pagination not found")
        return html

    tags = ul.find_all("button")

    max_page = 1
    for tag in tags:
        txt = tag.text.strip()
        if txt.isnumeric():
            max_page = max(max_page, int(txt))

    max_page = min(max_page_limit, max_page)

    # 2ページ目以降
    for page in range(2, max_page + 1):
        try:
            # ページ全体を一番下までスクロール
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.8)

            # ページ番号ボタンを待つ
            btn = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, f"//button[@aria-label='Go to page {page}']")
                )
            )

            # ボタンを中央にスクロール
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", btn
            )
            time.sleep(0.5)

            # JS click（最も安定）
            driver.execute_script("arguments[0].click();", btn)

            # ページ遷移待ち
            time.sleep(1.2)

            html_list.append(driver.page_source)

        except Exception as e:
            print(f"skip: {page}, error={e}")
            continue

    return "\n".join(html_list)


def fetch_html(url: str, company_id: str):
    """
    JavaScript 実行後の HTML を取得する Selenium 専用 fetcher。
    全社共通で使用する。
    - AXA のような JS 生成ページに必須
    - Aflac / FWD / Asahi など JS 依存ページにも対応
    """

    driver = create_driver_regular()
    if company_id.lower() == "aflac":
        driver = create_driver_aflac()

    if company_id.lower() == "fwdlife":
        ret = fetch_html_Fwdlife(url=url, driver=driver)
    else:
        ret = fetch_html_regular(url=url, driver=driver)

    driver.quit()

    return ret
