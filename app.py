import json
import os
from fastapi import FastAPI, HTTPException
from oauth2client.service_account import ServiceAccountCredentials
import gspread

app = FastAPI()

# 環境変数から `credentials.json` の内容を取得
credentials_json = os.getenv("GOOGLE_CREDENTIALS")
if credentials_json is None:
    raise ValueError("環境変数 GOOGLE_CREDENTIALS が設定されていません")

# credentials.json を Python オブジェクトとしてロード
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
    指定した product_id の最新の価格を取得します。
    優先順位は、現場ID > 取引先ID > 会社共通価格。
    シートには、最低限以下のカラムが必要です：
      - product_id
      - price（会社共通価格）
      - customer_id（任意、取引先の場合）
      - site_id（任意、現場の場合）
      - new_price（更新後の価格。取引先または現場用）
    """
    try:
        sheet = client.open_by_key(SHEET_ID).sheet1
        records = sheet.get_all_records()

        # 初期値として会社共通価格を取得
        company_price = None
        for record in records:
            if record.get("product_id") == product_id:
                if "price" in record:
                    company_price = record["price"]
                # まず、現場IDが指定され、該当レコードがあれば返す
                if site_id and record.get("site_id") == site_id:
                    return {
                        "product_id": product_id,
                        "price": record.get("new_price", company_price),
                        "source": "site"
                    }
                # 次に、取引先IDが指定され、該当レコードがあれば返す
                if customer_id and record.get("customer_id") == customer_id:
                    return {
                        "product_id": product_id,
                        "price": record.get("new_price", company_price),
                        "source": "customer"
                    }
        # どちらも該当しなければ、会社共通価格を返す
        if company_price is not None:
            return {"product_id": product_id, "price": company_price, "source": "company"}
        raise HTTPException(status_code=404, detail="Product not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update_price")
def update_price(product_id: str, new_price: float, customer_id: str = None, site_id: str = None):
    """
    指定した product_id の価格を更新し、変更履歴を記録します。
    条件に応じて更新対象を選択します：
      - site_id が指定された場合 → その現場の価格を更新
      - customer_id が指定された場合 → その取引先の価格を更新
      - どちらも指定されなければ → 会社共通価格を更新
    ※ このコード例では、更新対象のセルの列番号は仮定しています。
      シートの実際の構成に合わせて update_cell の引数を調整してください。
    """
    try:
        sheet = client.open_by_key(SHEET_ID).sheet1
        records = sheet.get_all_records()
        updated = False

        # 更新対象行のインデックス (2行目以降がデータ)
        for idx, record in enumerate(records, start=2):
            if record.get("product_id") == product_id:
                # 現場IDが指定されている場合
                if site_id and record.get("site_id") == site_id:
                    sheet.update_cell(idx, 2, new_price)  # 例：列2が価格列
                    updated = True
                    break
                # 取引先IDが指定されている場合
                elif customer_id and record.get("customer_id") == customer_id:
                    sheet.update_cell(idx, 2, new_price)
                    updated = True
                    break
                # どちらも指定されていない場合は会社共通価格を更新
                elif not customer_id and not site_id:
                    sheet.update_cell(idx, 2, new_price)
                    updated = True
                    break
        if updated:
            return {"message": "Price updated successfully"}
        raise HTTPException(status_code=404, detail="Product not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
