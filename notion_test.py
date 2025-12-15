import datetime
import glob
import json
import os
import pprint
import re
import time
from collections.abc import Generator
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import urlparse

import click
import requests
from google.oauth2.credentials import Credentials

# Google Sheets設定
SPREADSHEET_ID = "17o8WlEqAS9QXe5U34Yux-z40uWuUlycf8d3gpuaY5D0"
SHEET_NAME = "シート1"

USER_INFO = json.load(
    open(os.path.join(os.path.dirname(__file__), "user.json"), encoding="utf-8")
)


# Notion API設定
NOTION_API_SECRET = USER_INFO["notion_api_secret"]
NOTION_DATABASE_ID = "17e49c28c38e80f1837efca5e436a572"
NOTION_API_URL = "https://api.notion.com/v1/pages"


# サンプルデータ
data = {
    "title": "This is the title",
    "url": "http://foo.com/bar",
    "tags": ["tagA", "tagB"],
    "priority": None,
}


@dataclass
class PaperLink:
    title: str
    url: str
    tags: list[str]
    priority: int
    note: str
    created_at: Optional[datetime.datetime]


# Google Sheets APIの認証
def get_google_credentials() -> Credentials:
    client_id = (
        "456242472377-gh72p5ub9qfd22imb2obs66htm6e2i1d.apps.googleusercontent.com"
    )

    client_secret_file = glob.glob(
        os.path.join(os.path.dirname(__file__), "client_secret_*.json")
    )[0]
    client_secret_info = json.load(open(client_secret_file, "r"))
    client_secret = client_secret_info["installed"]["client_secret"]

    oauth_info = json.load(
        open(os.path.join(os.path.dirname(__file__), "oauth_info.json"), "r")
    )

    credentials = Credentials(
        token=oauth_info["access_token"],
        refresh_token=oauth_info["refresh_token"],
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    #
    # credentials.refresh(Request())
    return credentials


# Raindrop.io API設定
RAINDROP_API_TOKEN = USER_INFO["raindrop_api_token"]

# Raindrop.ioのAPIヘッダー
raindrop_headers = {"Authorization": f"Bearer {RAINDROP_API_TOKEN}"}


RAINDROP_SRC_COLLECTION_NAME = "論文/unread"
RAINDROP_DST_COLLECTION_NAME = "論文/read"


TargetSites = [
    "aaai.org",
    "ametsoc.org",
    "arxiv.org",
    "copernicus.org",
    "dl.acm.org",
    "iclr.cc",
    "icml.cc",
    "ieeexplore.ieee.org",
    "mdpi.org",
    "nature.com",
    "nips.cc",
    "onlinelibrary.wiley.com",
    "openaccess.thecvf.com",
    "openreview.net",
    "researchsquare.com",
    "science.org",
    "sciencedirect.com",
    "semanticscholar.org",
    "www.nature.com",
]


def get_collection_id(name: str) -> int:
    url = "https://api.raindrop.io/rest/v1/collections"
    response = requests.get(url, headers=raindrop_headers)
    response.raise_for_status()
    collections = response.json()["items"]

    for collection in collections:
        if collection["title"] == name:
            assert type(collection["_id"]) is int, "Collection ID must be an integer"
            return collection["_id"]
    else:
        raise ValueError(f"フォルダ '{name}' が見つかりません。")


def move_bookmark(bm, dst_coll_name: str) -> None:
    assert dst_coll_name is not None

    move_url = f"https://api.raindrop.io/rest/v1/raindrop/{bm['_id']}"
    move_data = {"collection": {"$id": get_collection_id(dst_coll_name)}}
    response = requests.put(move_url, headers=raindrop_headers, json=move_data)
    response.raise_for_status()


def read_raindrop_bookmarks(
    src_coll_name: str,
    dst_coll_name: str | None,
    limit: int,
    api_token: str | None = None,
) -> Generator[PaperLink, Tuple[str, Optional[str], Optional[str]], None]:
    if api_token is None:
        api_token = RAINDROP_API_TOKEN

    assert limit > 0

    coll_id = get_collection_id(src_coll_name)
    bookmarks = []

    PER_PAGE = 20

    i = 0
    while True:
        url = f"https://api.raindrop.io/rest/v1/raindrops/{coll_id}?perpage={PER_PAGE}&page={i}&sort=-created"
        response = requests.get(url, headers=raindrop_headers)
        response.raise_for_status()

        bookmarks = response.json()["items"]

        # pprint.pprint(bookmarks)

        if len(bookmarks) == 0:
            return

        for bm in bookmarks:
            print(f"{bm=}")
            if "link" not in bm:
                continue

            if m := re.search(r"p([1-5])", bm.get("excerpt", "")):
                priority = int(m.group(1))
            else:
                priority = 3
            data = PaperLink(
                title=bm["title"],
                url=bm["link"],
                tags=[],
                priority=priority,
                note=bm.get("excerpt", ""),
                created_at=datetime.datetime.now(),
            )

            yield data

            if dst_coll_name:
                move_bookmark(bm, dst_coll_name)

            i += 1
            if i >= limit:
                return


# 新しいページを作成
def create_notion_page(data: PaperLink, dry_run: bool = False) -> None:
    assert data.title is not None, "タイトルが指定されていません"
    assert data.url, "URLが指定されていません"

    headers = {
        "Authorization": f"Bearer {NOTION_API_SECRET}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",  # 使用するNotion APIのバージョン
    }

    # ペイロード（リクエストボディ）
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "タイトル": {  # タイトルフィールド（データベースでタイトルとして設定されているプロパティ名）
                "title": [{"text": {"content": data.title}}]
            },
            "URL": {  # メタデータ（データベースのURLフィールド名に合わせる）
                "url": data.url
            },
            "タグ": {  # タグフィールド（マルチセレクト形式で設定されているプロパティ名）
                "multi_select": [{"name": tag} for tag in data.tags]
            },
            "優先度": {  # 優先度フィールド（数値形式で設定されているプロパティ名）
                "number": data.priority
            },
            "作成日時": {  # 作成日時フィールド（日時形式で設定されているプロパティ名）
                "date": {
                    "start": data.created_at.isoformat() if data.created_at else None
                }
            },
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": data.note}}]
                },
            }
        ],
    }

    if not dry_run:
        # Notion APIにリクエスト
        response = requests.post(NOTION_API_URL, headers=headers, json=payload)

        # レスポンスの確認
        if response.status_code == 200:
            print("✅️ ページが作成されました:")
            pprint.pprint(response.json())
        else:
            print(f"⚠️ エラー: {response.status_code}")
            print(response.json())
            raise RuntimeError("エラーが発生しました")
    else:
        print("Dry run:")
        pprint.pprint(payload)


@click.command()
@click.option("--dry-run", is_flag=True, default=False, help="Dry run")
@click.option("--delete/--no-delete", is_flag=True, help="Delete", default=True)
@click.option("--limit", type=int, default=10, help="Limit")
@click.option("--interval", type=int, default=2, help="Interval")
@click.option("--source", type=click.Choice(["google", "raindrop"]), default="google")
def main(
    source: str, delete: bool, dry_run: bool, limit: int = 10, interval: int = 2
) -> None:
    assert source in ["google", "raindrop"], "Invalid source"

    if dry_run is True:
        print(f"Let delete False, because {dry_run=}")
        delete = False

    data: PaperLink

    if delete is True:
        dst_coll_name = RAINDROP_DST_COLLECTION_NAME
    else:
        dst_coll_name = None
    for data in read_raindrop_bookmarks(
        RAINDROP_SRC_COLLECTION_NAME, dst_coll_name=dst_coll_name, limit=limit
    ):
        print(f"{data=}")
        parsed_url = urlparse(data.url)
        hostname = parsed_url.hostname
        if hostname not in TargetSites:
            print(f"Skip: {hostname}: {data.url}")
            continue
        print("\n\n----------------")
        pprint.pprint(data)
        create_notion_page(data, dry_run)
        if limit > 1:
            time.sleep(interval)


# 実行
if __name__ == "__main__":
    main()
