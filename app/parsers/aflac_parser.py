# app/parsers/aflac_parser.py

from bs4 import BeautifulSoup

from app.models import NewsItem
from utils.adj_utils import adj_dlt


def parse_news(
    html: str,
    url: str,
    url_type: str,
    company_id: str,
    company_name: str,
    company_url: str,
    url_id: str,
    year: str,
) -> list[NewsItem]:

    soup = BeautifulSoup(html, "html.parser")
    results: list[NewsItem] = []

    # Aflac のニュース一覧は article.news__article
    articles = soup.select("article.news__article")
    if not articles:
        return results

    for art in articles:
        # 日付
        date_el = art.select_one("time.news__date")
        # タイトル
        title_el = art.select_one("h3.news__title")
        # PDFリンク
        link_el = art.select_one("a[href]")

        if not (date_el and title_el and link_el):
            continue

        raw_date = date_el.get_text(strip=True)
        raw_title = title_el.get_text(strip=True)
        raw_link = link_el["href"]
        # print(raw_date, raw_title, raw_link)
        # Aflac のリンクは /static/... なので company_url を使って絶対URL化
        # adj_dlt が内部で絶対URL化するのでそのまま渡してOK
        date, link, title = adj_dlt(
            raw_date,
            raw_link,
            raw_title,
            company_url,
            url,
        )

        results.append(
            NewsItem(
                url_id=url_id,
                company_id=company_id,
                company_name=company_name,
                company_url=company_url,
                url_type=url_type,
                url=url,
                article_type="ニュースリリース",
                article_date=date,
                article_title=title,
                article_url=link,
                is_new="False",
            )
        )

    return results


def parse_info(
    html: str,
    url: str,
    url_type: str,
    company_id: str,
    company_name: str,
    company_url: str,
    url_id: str,
    year: str,
) -> list[NewsItem]:

    soup = BeautifulSoup(html, "html.parser")
    results: list[NewsItem] = []

    # Aflac お知らせ一覧は ul.toipcsFlex > li > dl
    items = soup.select("ul.toipcsFlex > li > dl")
    if not items:
        return results

    for dl in items:
        date_el = dl.select_one("dt")
        link_el = dl.select_one("dd a[href]")

        if not (date_el and link_el):
            continue

        raw_date = date_el.get_text(strip=True)
        raw_title = link_el.get_text(strip=True)
        raw_link = link_el["href"]

        # adj_dlt で正規化（AXA と同じ処理）
        date, link, title = adj_dlt(
            raw_date,
            raw_link,
            raw_title,
            company_url,
            url,
        )

        results.append(
            NewsItem(
                url_id=url_id,
                company_id=company_id,
                company_name=company_name,
                company_url=company_url,
                url_type=url_type,
                url=url,
                article_type="お知らせ",
                article_date=date,
                article_title=title,
                article_url=link,
                is_new="False",
            )
        )

    return results
