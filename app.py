import json
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from oauth2client.service_account import ServiceAccountCredentials
import gspread

from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

# CORS設定：React（localhost:3000）からのリクエストを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=[""http://localhost:3000""],  # 本番では制限した方が安全（例: ["http://localhost:3000"]）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 環境変数から credentials.json の内容を取得
credentials_json = os.getenv("GOOGLE_CREDENTIALS")
if credentials_json is None:
    raise ValueError("環境変数 GOOGLE_CREDENTIALS が設定されていません")

# JSON 文字列を Python の辞書に変換
creds_dict = json.loads(credentials_json)

# Google Sheets API の認証設定
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# スプレッドシートのIDを設定
SHEET_ID = "1iVxcgSJbT4FoCr-322hbzjiNdsTkTJ8ZviG1dPKUgoU"

@app.get("/")
def root():
    return {"message": "Waterproof AI API is running!"}

@app.get("/get_price")
def get_price(product_id: str, customer_id: str = None, site_id: str = None):
    """
    指定された product_id に対し、以下3つの価格のうち存在するものの中で最安値を返します：
      - 会社共通価格（products シートの price）
      - 取引先ごとの価格（customer_prices シートの price）【customer_id が指定された場合のみ】
      - 現場ごとの価格（site_prices シートの price）【site_id が指定された場合のみ】
    """
    try:
        # 1. 会社共通価格
        sheet_products = client.open_by_key(SHEET_ID).worksheet("products")
        products = sheet_products.get_all_records()
        company_price = None
        for rec in products:
            if rec.get("product_id") == product_id:
                company_price = rec.get("price")
                break

        # 2. 取引先ごとの価格
        customer_price = None
        if customer_id:
            sheet_customer = client.open_by_key(SHEET_ID).worksheet("customer_prices")
            customer_records = sheet_customer.get_all_records()
            for rec in customer_records:
                if rec.get("product_id") == product_id and rec.get("customer_id") == customer_id:
                    customer_price = rec.get("price")
                    break

        # 3. 現場ごとの価格
        site_price = None
        if site_id:
            sheet_site = client.open_by_key(SHEET_ID).worksheet("site_prices")
            site_records = sheet_site.get_all_records()
            for rec in site_records:
                if rec.get("product_id") == product_id and rec.get("site_id") == site_id:
                    site_price = rec.get("price")
                    break

        available_prices = []
        if company_price is not None:
            available_prices.append(("company", float(company_price)))
        if customer_price is not None:
            available_prices.append(("customer", float(customer_price)))
        if site_price is not None:
            available_prices.append(("site", float(site_price)))

        if not available_prices:
            raise HTTPException(status_code=404, detail="Product not found")

        # 最安値を選択
        cheapest_source, cheapest_price = min(available_prices, key=lambda x: x[1])
        return {
            "product_id": product_id,
            "lowest_price": cheapest_price,
            "source": cheapest_source,
            "details": {
                "company_price": company_price,
                "customer_price": customer_price,
                "site_price": site_price
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update_price")
def update_price(product_id: str, new_price: float, customer_id: str = None, site_id: str = None):
    """
    指定された product_id の価格を更新し、変更履歴を記録します。
    更新対象は以下の通り：
      - site_id が指定された場合 → site_prices シートを更新
      - customer_id が指定された場合 → customer_prices シートを更新
      - どちらも指定されなければ → products シート（会社共通価格）を更新
    更新後、変更前と変更後の価格および更新日時を price_history シートに記録します。
    """
    try:
        updated = False
        old_price = None

        # 現場ごとの価格更新
        if site_id:
            sheet_site = client.open_by_key(SHEET_ID).worksheet("site_prices")
            records = sheet_site.get_all_records()
            for idx, rec in enumerate(records, start=2):
                if rec.get("product_id") == product_id and rec.get("site_id") == site_id:
                    old_price = rec.get("price")
                    sheet_site.update_cell(idx, 3, new_price)  # 例: 価格が3列目
                    updated = True
                    break
        # 取引先ごとの価格更新
        elif customer_id:
            sheet_customer = client.open_by_key(SHEET_ID).worksheet("customer_prices")
            records = sheet_customer.get_all_records()
            for idx, rec in enumerate(records, start=2):
                if rec.get("product_id") == product_id and rec.get("customer_id") == customer_id:
                    old_price = rec.get("price")
                    sheet_customer.update_cell(idx, 3, new_price)
                    updated = True
                    break
        # 会社共通価格更新
        else:
            sheet_products = client.open_by_key(SHEET_ID).worksheet("products")
            records = sheet_products.get_all_records()
            for idx, rec in enumerate(records, start=2):
                if rec.get("product_id") == product_id:
                    old_price = rec.get("price")
                    sheet_products.update_cell(idx, 2, new_price)  # 例: 価格が2列目
                    updated = True
                    break

        if not updated:
            raise HTTPException(status_code=404, detail="Product not found or no matching record to update")

        # 変更履歴を記録する: price_history シートに追記
        sheet_history = client.open_by_key(SHEET_ID).worksheet("price_history")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet_history.append_row([
            None,                   # record_id: 自動的に生成されるか空欄でOK
            product_id,
            customer_id if customer_id else "",
            site_id if site_id else "",
            old_price,
            new_price,
            timestamp
        ])

        return {
            "message": "Price updated successfully",
            "product_id": product_id,
            "old_price": old_price,
            "new_price": new_price,
            "timestamp": timestamp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_price_all")
def get_price_all():
    sheet = client.open_by_key(SHEET_ID).worksheet("products")
    records = sheet.get_all_records()
    result = []

    for row in records:
        result.append({
            "product_id": row["product_id"],
            "product_name": row.get("product_name", ""),
            "lowest_price": row["price"]
        })

    return result
