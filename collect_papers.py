import datetime
import glob
import itertools
import json
import os
from typing import Optional

import click
import gspread
import requests
from google.oauth2.credentials import Credentials

RAINDROP_SRC_COLLECTION_NAME = "論文/unread"
RAINDROP_DST_COLLECTION_NAME = "論文/read"


TargetSites = [
    "arxiv.org",
    "nips.cc",
    "iclr.cc",
    "openreview.net",
    "openaccess.thecvf.com",
    "ametsoc.org",
    "dl.acm.org",
    "onlinelibrary.wiley.com",
    "mdpi.org",
    "sciencedirect.com",
    "semanticscholar.org",
    "ieeexplore.ieee.org",
    "icml.cc",
    "nature.com",
    "science.org",
    "aaai.org",
]


class RaindropReader(object):
    def __init__(
        self,
        src_coll_name: str,
        dst_coll_name: Optional[str] = None,
        api_token: Optional[str] = None,
        dry_run: bool = False,
    ):
        if api_token is None:
            api_token = (
                open(os.path.join(os.path.dirname(__file__), "raindrop_token.txt"))
                .read()
                .strip()
            )
        self.src_coll_name = src_coll_name
        self.dst_coll_name = dst_coll_name
        self.api_token = api_token
        self.dry_run = dry_run

    def get_collection_id(self, name: str):
        url = "https://api.raindrop.io/rest/v1/collections"
        response = requests.get(url, headers=raindrop_headers)
        response.raise_for_status()
        collections = response.json()["items"]

        for collection in collections:
            if collection["title"] == name:
                return collection["_id"]
        else:
            raise ValueError(f"フォルダ '{name}' が見つかりません。")

    def __iter__(self):
        coll_id = self.get_collection_id(self.src_coll_name)
        bookmarks = []

        PER_PAGE = 20

        i = 0
        while True:
            url = f"https://api.raindrop.io/rest/v1/raindrops/{coll_id}?perpage={PER_PAGE}&page={i}&sort=-created"
            response = requests.get(url, headers=raindrop_headers)
            response.raise_for_status()

            bookmarks = response.json()["items"]

            if len(bookmarks) == 0:
                return

            for bm in bookmarks:
                yield bm

                if self.dst_coll_name:
                    self.move_bookmark(
                        bm,
                    )

            i += 1

    def move_bookmark(self, bm):
        if opt_dry_run:
            return

        assert self.dst_coll_name is not None

        move_url = f"https://api.raindrop.io/rest/v1/raindrop/{bm['_id']}/move"
        move_data = {"collectionId": self.get_collection_id(self.dst_coll_name)}
        response = requests.put(move_url, headers=raindrop_headers, json=move_data)
        response.raise_for_status()


opt_dry_run = False

# Raindrop.io API設定
RAINDROP_API_TOKEN = (
    open(os.path.join(os.path.dirname(__file__), "raindrop_token.txt")).read().strip()
)


NOTION_SECRET = "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"
NOTION_DATABASE_ID = "17e49c28c38e80f1837efca5e436a572"

# Google Sheets設定
SPREADSHEET_ID = "17o8WlEqAS9QXe5U34Yux-z40uWuUlycf8d3gpuaY5D0"
SHEET_NAME = "シート1"


# Google Sheets APIの認証
def get_credentials():
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


# Raindrop.ioのAPIヘッダー
raindrop_headers = {"Authorization": f"Bearer {RAINDROP_API_TOKEN}"}


# 1. Raindrop.ioのフォルダIDを取得

# 2. ブックマークを取得


# 3. Google Sheetsにデータを書き込む
def write_to_spreadsheet(bookmarks):
    if opt_dry_run:
        return
    cred = get_credentials()
    cli = gspread.authorize(cred)

    sheet = cli.open_by_key(SPREADSHEET_ID)

    tags = [
        "Proj関連",
        "気象",
        "データ同化",
        "Sim/PDE",
        "LLM",
        "HPC",
    ]

    # ヘッダーの書き込み
    for i, h in enumerate(["Title", "優先度(1-5)", "URL", "Note", "Created At"] + tags):
        col = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[i]
        sheet.values_update(
            f"{col}2",
            params={"valueInputOption": "USER_ENTERED"},
            body={"values": [[h]]},
        )

    # データの下端を取得
    last_row = len(sheet.sheet1.col_values(1))
    print(f"{last_row=}")

    # ブックマークデータの書き込み

    new_rows_data = []

    for bm in bookmarks:
        created = datetime.datetime.strptime(bm["created"], "%Y-%m-%dT%H:%M:%S.%fZ")
        new_rows_data.append(
            [
                bm["title"],
                "3",
                bm["link"],
                bm["note"],
                created.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )
    start_cell = f"A{last_row + 1}"
    print(f"{start_cell=}")
    sheet.values_update(
        start_cell,
        params={"valueInputOption": "USER_ENTERED"},
        body={"values": new_rows_data},
    )


# 4. Raindrop.ioのブックマークを削除


# メイン処理
@click.command()
@click.option("--dry-run", is_flag=True, help="Dry run")
def main(dry_run: bool = False):
    global opt_dry_run
    opt_dry_run = dry_run

    def filter_by_url(bm):
        return any(t in bm["link"] for t in TargetSites)

    it = filter(filter_by_url, RaindropReader(RAINDROP_SRC_COLLECTION_NAME))

    for bm in itertools.islice(it, 10):
        print(bm)

    exit(0)

    try:
        # フォルダIDを取得
        collection_id = get_collection_id(RAINDROP_SRC_COLLECTION_NAME)
        print(f"{collection_id=}")

        # ブックマークを取得
        bookmarks = get_bookmarks(collection_id)
        if not bookmarks:
            print("ブックマークが見つかりません。")
            return

        bookmarks2 = []
        for bm in bookmarks:
            for site in TargetSites:
                if site in bm["link"]:
                    bookmarks2.append(bm)
                    break

        bookmarks = bookmarks2

        import pprint

        pprint.pprint(bookmarks)

        # for bm in bookmarks:
        #     print(f"{bm['title']}: {bm['link']}")

        # # Google Sheetsに書き込む
        write_to_spreadsheet(bookmarks)
        print(
            f"{len(bookmarks)} 件のブックマークをGoogle Spreadsheetに書き込みました。"
        )

        # Raindrop.ioのブックマークを削除
        move_bookmarks(bookmarks)
        print(f"{len(bookmarks)} 件のブックマークをRaindrop.ioから削除しました。")

    except Exception:
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
