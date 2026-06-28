from bs4 import BeautifulSoup

from app.models import NewsItem
from utils.adj_utils import adj_dlt


def parse_press(
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

    # FWD のニュース一覧は ListView__ListItem-sc-* に入っている
    items = soup.find_all("div", class_=lambda c: c and c.startswith("ListView__ListItem-sc"))
    if not items:
        return results

    for item in items:
        # aタグ（リンク）
        link_el = item.find("a", href=True)
        if not link_el:
            continue

        raw_link = link_el["href"]

        # 日付
        date_el = item.find("div", class_=lambda c: c and c.startswith("ListView__ListItemDate-sc"))
        # タイトル
        title_el = item.find("div", class_=lambda c: c and c.startswith("ListView__ListItemTitle-sc"))

        if not (date_el and title_el):
            continue

        raw_date = date_el.get_text(strip=True)
        raw_title = title_el.get_text(strip=True)

        # adj_dlt で正規化
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
