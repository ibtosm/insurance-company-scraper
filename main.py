# -----------------------------
# ① 標準ライブラリ
# -----------------------------
import csv
import json
import pkgutil
import re
import sys
from pathlib import Path
from urllib.parse import ParseResult, urlparse

# -----------------------------
# ② プロジェクト内 import
# -----------------------------
import app.parsers as parsers_pkg
from app.fetcher import fetch_html
from app.models import NewsItem
from utils.csv_utils import load_csv, write_csv
from utils.file_utils import backup_file

# -----------------------------
# ③ グローバル設定
# -----------------------------
encoding = "utf-8"
DATA_INPUT_DIR: Path = Path("data/input")
DATA_OUTPUT_DIR: Path = Path("data/output")

# -----------------------------
# ④ parser 自動ロード
# -----------------------------
PARSER_MODULES = {}

for loader, module_name, is_pkg in pkgutil.iter_modules(path=parsers_pkg.__path__):
    module = __import__(name=f"app.parsers.{module_name}", fromlist=[module_name])
    PARSER_MODULES[module_name] = module


# -----------------------------
# ⑤ resolve_parser
# -----------------------------
def resolve_parser(path: str):
    """
    "axa_parser.parse_news" のような文字列を
    実際の Python 関数に変換する。
    """
    module_name, func_name = path.split(sep=".")
    module = PARSER_MODULES[module_name]
    return getattr(module, func_name)


# -----------------------------
# ⑥ mapping.json 読み込み
# -----------------------------
mapping_path: Path = Path("config/mapping.json")
mapping_json = json.loads(mapping_path.read_text(encoding=encoding))

mapping = {}
for company_id, types in mapping_json.items():
    mapping[company_id] = {}
    for url_type, parser_path in types.items():
        mapping[company_id][url_type] = resolve_parser(path=parser_path)


# -----------------------------
# ⑦ 以下、既存の関数群
# -----------------------------
def normalize_mode(value: str) -> str:
    v = value.strip().lower()
    if v in ("t", "true"):
        return "True"
    if v in ("f", "false"):
        return "False"
    return ""


def load_companies():
    companies = {}
    with open(file=DATA_INPUT_DIR / "companies.csv", encoding=encoding) as f:
        reader = csv.DictReader(f)
        for row in reader:
            companies[row["company_id"]] = row
    return companies


def load_urls(entry_mode: str, company_filter: str | None = None) -> list[dict]:
    urls = []
    with open(file=DATA_INPUT_DIR / "urls.csv", encoding=encoding) as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_mode: str = normalize_mode(value=row["mode"])
            if row_mode != entry_mode:
                continue

            company_id = row["company_id"]

            # 会社名がコメント化されている場合
            if company_id.startswith("#"):
                continue
            # 会社フィルタが指定されている場合
            if company_filter and company_id != company_filter:
                continue

            url_type: str = row["url_type"]
            url: str = row["url"]

            row["url_id"] = generate_url_id(company_id, url_type, url)
            row["year"] = extract_year_from_url(url=url)

            urls.append(row)
    return urls


def generate_url_id(company_id: str, url_type: str, url: str) -> str:
    parsed: ParseResult = urlparse(url=url)
    path: str = parsed.path.strip("/")
    normalized_path: str = path.replace("/", "_")
    return f"{company_id}@{url_type}@{normalized_path}"


def extract_year_from_url(url: str) -> str:
    m = re.search(r"(20\d{2})", url)
    return m.group(1) if m else "0000"


def scrape_urls(urls: list[dict], companies: dict) -> list[NewsItem]:
    all_results = []
    total: int = len(urls)

    for idx, entry in enumerate(urls, start=1):
        company_id = entry["company_id"]
        url = entry["url"]
        url_type = entry["url_type"]
        url_id = entry["url_id"]
        year = entry["year"]

        company_name = companies[company_id]["company_name"]
        company_url = companies[company_id]["company_url"]

        print(f"[{idx}/{total}] Scraping {company_name} ({url_type}) → {url}")

        parser_func = mapping[company_id][url_type]
        if not parser_func:
            print(f"  → parser not found for {company_id}, skipped")
            continue

        html = fetch_html(url=url, company_id=company_id)
        with open(file=".debug.html", mode="w", encoding=encoding) as f:
            f.write(html)

        results = parser_func(
            html=html,
            url=url,
            url_type=url_type,
            company_id=company_id,
            company_name=company_name,
            company_url=company_url,
            url_id=url_id,
            year=year,
        )

        all_results.extend(results)

    return all_results


def save_results(results: list[NewsItem], entry_mode: str):
    output_file: Path = DATA_OUTPUT_DIR / f"scraped_results_{entry_mode}.csv"

    rows = []
    for item in results:
        rows.append(
            {
                "url_id": item.url_id,
                "company_id": item.company_id,
                "company_name": item.company_name,
                "company_url": item.company_url,
                "url_type": item.url_type,
                "url": item.url,
                "article_type": item.article_type,
                "article_date": item.article_date,
                "article_title": item.article_title,
                "article_url": item.article_url,
                "is_new": item.is_new,
            }
        )

    write_csv(path=output_file, rows=rows)


def merge_results_daily():
    true_file: Path = DATA_OUTPUT_DIR / "scraped_results_True.csv"
    false_file: Path = DATA_OUTPUT_DIR / "scraped_results_False.csv"
    merged_file: Path = DATA_OUTPUT_DIR / "scraped_results_merged.csv"

    # 前回の merged をバックアップ
    old_file: Path = backup_file(path=merged_file)

    # 差分判定用：前回の merged
    if old_file.exists():
        old_rows = load_csv(path=old_file)
    else:
        old_rows = []
    old_dict = {(row["article_date"], row["article_title"]) for row in old_rows}

    # 今回の材料：True + False
    true_rows = load_csv(path=true_file)
    false_rows = load_csv(path=false_file)
    # 新しい merged のベース（True + False の合計）
    new_dict = {}

    # False（過去）
    for row in false_rows:
        new_dict[(row["article_date"], row["article_title"])] = row

    # True（最新）
    for row in true_rows:
        new_dict[(row["article_date"], row["article_title"])] = row

    # 差分判定（old と new を比較）
    for url, row in new_dict.items():
        if url in old_dict:
            row["is_new"] = "False"
        else:
            row["is_new"] = "True"

    # 日付降順でソート
    merged_rows = list(new_dict.values())
    merged_rows.sort(key=lambda r: r["article_date"], reverse=True)
    print(len(merged_rows))

    write_csv(merged_file, merged_rows)
    print("Merged file created:", merged_file)


def main():
    if len(sys.argv) < 2:
        print("mode を指定してください（T / F / True / False）")
        print("T: 最新 / F: 過去")
        return

    entry_mode_raw: str = sys.argv[1]
    entry_mode: str = normalize_mode(value=entry_mode_raw)

    if entry_mode == "":
        print(f"不正な mode です: {entry_mode_raw}")
        return

    # 会社IDフィルタ（任意）
    company_filter: str | None = sys.argv[2].strip() if len(sys.argv) >= 3 else None

    companies = load_companies()
    urls = load_urls(entry_mode=entry_mode, company_filter=company_filter)

    all_results: list[NewsItem] = scrape_urls(urls, companies)
    save_results(results=all_results, entry_mode=entry_mode)

    print("Scraping completed.")
    if company_filter is None:
        merge_results_daily()
        print("Merge completed.")


if __name__ == "__main__":
    main()
