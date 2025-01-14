import os

import requests
# import gspread
# from google.oauth2.service_account import Credentials

# Raindrop.io API設定
RAINDROP_API_TOKEN = (
    open(os.path.join(os.path.dirname(__file__), "raindrop_token.txt")).read().strip()
)


RAINDROP_COLLECTION_NAME = "論文/unread"

# Google Sheets設定
# SPREADSHEET_NAME = "Raindrop Bookmarks"

# # Google Sheets APIの認証
# SERVICE_ACCOUNT_FILE = "path/to/your/service_account.json"
# credentials = Credentials.from_service_account_file(
#     SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]
# )
# gc = gspread.authorize(credentials)

# Raindrop.ioのAPIヘッダー
headers = {"Authorization": f"Bearer {RAINDROP_API_TOKEN}"}


# 1. Raindrop.ioのフォルダIDを取得
def get_collection_id():
    url = "https://api.raindrop.io/rest/v1/collection"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    collections = response.json()["items"]

    for collection in collections:
        if collection["title"] == RAINDROP_COLLECTION_NAME:
            return collection["_id"]
    raise ValueError(f"フォルダ '{RAINDROP_COLLECTION_NAME}' が見つかりません。")


# 2. ブックマークを取得
def get_bookmarks(collection_id):
    url = f"https://api.raindrop.io/rest/v1/raindrops/{collection_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["items"]


# 3. Google Sheetsにデータを書き込む
# def write_to_spreadsheet(bookmarks):
#     try:
#         # スプレッドシートを開くか、新規作成
#         sheet = gc.open(SPREADSHEET_NAME).sheet1
#     except gspread.SpreadsheetNotFound:
#         sheet = gc.create(SPREADSHEET_NAME).sheet1

#     # ヘッダーの書き込み
#     sheet.update("A1", [["Title", "URL", "Tags", "Created At"]])

#     # ブックマークデータの書き込み
#     rows = [
#         [bm["title"], bm["link"], ", ".join(bm["tags"]), bm["created"]]
#         for bm in bookmarks
#     ]
#     sheet.update("A2", rows)


# 4. Raindrop.ioのブックマークを削除
# def delete_bookmarks(bookmarks):
#     for bookmark in bookmarks:
#         url = f"https://api.raindrop.io/rest/v1/raindrop/{bookmark['_id']}"
#         response = requests.delete(url, headers=headers)
#         response.raise_for_status()


# メイン処理
def main():
    try:
        # フォルダIDを取得
        collection_id = get_collection_id()

        # ブックマークを取得
        bookmarks = get_bookmarks(collection_id)
        if not bookmarks:
            print("ブックマークが見つかりません。")
            return

        # # Google Sheetsに書き込む
        # write_to_spreadsheet(bookmarks)
        # print(f"{len(bookmarks)} 件のブックマークをGoogle Spreadsheetに書き込みました。")

        # # Raindrop.ioのブックマークを削除
        # delete_bookmarks(bookmarks)
        # print(f"{len(bookmarks)} 件のブックマークをRaindrop.ioから削除しました。")

    except Exception as e:
        print(f"エラーが発生しました: {e}")


if __name__ == "__main__":
    main()
