import datetime
import glob
import json
import os

import gspread
import requests
from google.oauth2.credentials import Credentials

# Raindrop.io API設定
RAINDROP_API_TOKEN = (
    open(os.path.join(os.path.dirname(__file__), "raindrop_token.txt")).read().strip()
)


RAINDROP_COLLECTION_NAME = "論文/unread"

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
def get_collection_id():
    url = "https://api.raindrop.io/rest/v1/collections"
    response = requests.get(url, headers=raindrop_headers)
    response.raise_for_status()
    collections = response.json()["items"]

    for collection in collections:
        if collection["title"] == RAINDROP_COLLECTION_NAME:
            return collection["_id"]
    else:
        raise ValueError(f"フォルダ '{RAINDROP_COLLECTION_NAME}' が見つかりません。")


# 2. ブックマークを取得
def get_bookmarks(collection_id):
    url = f"https://api.raindrop.io/rest/v1/raindrops/{collection_id}"
    response = requests.get(url, headers=raindrop_headers)
    response.raise_for_status()
    return response.json()["items"]


# 3. Google Sheetsにデータを書き込む
def write_to_spreadsheet(bookmarks):
    cred = get_credentials()
    cli = gspread.authorize(cred)

    sheet = cli.open_by_key(SPREADSHEET_ID)

    tags = [
        "Proj関連",
        "気象",
        "データ同化",
        "Sim/PDE",
        "LLM",
    ]

    # ヘッダーの書き込み
    for i, h in enumerate(["Title", "優先度(1-5)", "URL", "Tags", "Created At"] + tags):
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
                ", ".join(bm["tags"]),
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
def delete_bookmarks(bookmarks):
    for bookmark in bookmarks:
        url = f"https://api.raindrop.io/rest/v1/raindrop/{bookmark['_id']}"
        response = requests.delete(url, headers=raindrop_headers)
        response.raise_for_status()


# メイン処理
def main():
    try:
        # フォルダIDを取得
        collection_id = get_collection_id()
        print(f"{collection_id=}")

        # ブックマークを取得
        bookmarks = get_bookmarks(collection_id)
        if not bookmarks:
            print("ブックマークが見つかりません。")
            return

        bookmarks2 = []
        for bm in bookmarks:
            for site in ["arxiv.org", "nips.cc", "openreview.net"]:
                if site in bm["link"]:
                    bookmarks2.append(bm)
                    break

        bookmarks = bookmarks2

        for bm in bookmarks:
            print(f"{bm['title']}: {bm['link']}")

        # # Google Sheetsに書き込む
        write_to_spreadsheet(bookmarks)
        print(
            f"{len(bookmarks)} 件のブックマークをGoogle Spreadsheetに書き込みました。"
        )

        # Raindrop.ioのブックマークを削除
        delete_bookmarks(bookmarks)
        print(f"{len(bookmarks)} 件のブックマークをRaindrop.ioから削除しました。")

    except Exception:
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
