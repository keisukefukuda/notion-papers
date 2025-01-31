import json
import pprint

from pyzotero import zotero

USER_INFO = json.load(open("user.json", encoding="utf-8"))
API_KEY = USER_INFO["zotero_api_key"]
USER_ID = USER_INFO["zotero_user_id"]
LIBRARY_TYPE = "user"  # "groups" に変更するとグループライブラリを取得可能

zot = zotero.Zotero(USER_ID, LIBRARY_TYPE, API_KEY)
items = zot.top(limit=10)

for item in items:
    pprint.pprint(item)
