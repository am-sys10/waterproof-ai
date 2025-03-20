from fastapi import FastAPI
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = FastAPI()

# Google Sheets API の認証設定
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# スプレッドシートのID
SHEET_ID = "1iVxcgSJbT4FoCr-322hbzjiNdsTkTJ8ZviG1dPKUgoU"

@app.post("/update_price")
def update_price(product_id: str, new_price: int, customer_id: str = None, site_id: str = None):
    """
    価格を更新し、変更履歴を記録するAPI
    - 工事現場（site_id） ＞ 取引先（customer_id） ＞ 会社共通の優先順で価格を更新
    """

    sheet = client.open_by_key(SHEET_ID)
    history_sheet = sheet.worksheet("price_history")  # 履歴シート
    products_sheet = sheet.worksheet("products")  # 会社共通価格
    customer_prices_sheet = sheet.worksheet("customer_prices")  # 取引先価格
    site_prices_sheet = sheet.worksheet("site_prices")  # 現場価格

    old_price = None  # 変更前価格を記録
    updated = False  # 価格更新フラグ

    # 工事現場の価格を更新
    if site_id:
        site_prices = site_prices_sheet.get_all_records()
        for i, row in enumerate(site_prices, start=2):  # 1行目はヘッダー
            if row["商品ID"] == product_id and row["現場ID"] == site_id:
                old_price = row["現場単価"]
                site_prices_sheet.update_cell(i, 3, new_price)  # 変更後の価格を更新
                updated = True
                break

    # 取引先の価格を更新
    elif customer_id:
        customer_prices = customer_prices_sheet.get_all_records()
        for i, row in enumerate(customer_prices, start=2):
            if row["商品ID"] == product_id and row["取引先ID"] == customer_id:
                old_price = row["取引先単価"]
                customer_prices_sheet.update_cell(i, 3, new_price)
                updated = True
                break

    # 会社共通価格を更新
    else:
        products = products_sheet.get_all_records()
        for i, row in enumerate(products, start=2):
            if row["商品ID"] == product_id:
                old_price = row["会社共通単価"]
                products_sheet.update_cell(i, 3, new_price)
                updated = True
                break

    # 価格が更新された場合、履歴を記録
    if updated and old_price is not None and old_price != new_price:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history_sheet.append_row([None, product_id, customer_id or "", site_id or "", old_price, new_price, timestamp])

        return {
            "message": "価格が更新されました",
            "product_id": product_id,
            "old_price": old_price,
            "new_price": new_price,
            "updated_at": timestamp
        }

    return {"error": "価格の更新に失敗しました"}
