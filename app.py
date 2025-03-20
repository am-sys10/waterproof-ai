import json
import os
from fastapi import FastAPI, HTTPException
from oauth2client.service_account import ServiceAccountCredentials
import gspread

app = FastAPI()

# 環境変数から `credentials.json` のデータを取得
credentials_json = os.getenv("GOOGLE_CREDENTIALS")

if credentials_json is None:
    raise ValueError("環境変数 GOOGLE_CREDENTIALS が設定されていません")

# `credentials.json` を Python オブジェクトとしてロード
creds_dict = json.loads(credentials_json)

# `ServiceAccountCredentials` に渡す
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

# Google Sheets API に接続
client = gspread.authorize(creds)

# **スプレッドシート ID を設定**
SHEET_ID = "1iVxcgSJbT4FoCr-322hbzjiNdsTkTJ8ZviG1dPKUgoU"

@app.get("/")
def root():
    return {"message": "Waterproof AI API is running!"}

@app.get("/get_price")
def get_price(product_id: str):
    """ 指定した `product_id` の価格を取得する """
    try:
        sheet = client.open_by_key(SHEET_ID).sheet1  # 最初のシートを開く
        records = sheet.get_all_records()

        for record in records:
            if record.get("product_id") == product_id:
                return {"product_id": product_id, "price": record.get("price")}

        raise HTTPException(status_code=404, detail="Product not found")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update_price")
def update_price(product_id: str, new_price: float):
    """ 指定した `product_id` の価格を更新する """
    try:
        sheet = client.open_by_key(SHEET_ID).sheet1  # 最初のシートを開く
        records = sheet.get_all_records()

        for idx, record in enumerate(records, start=2):  # シートの行は 1 から始まるので 2 から
            if record.get("product_id") == product_id:
                sheet.update_cell(idx, 2, new_price)  # 価格を更新（列 2 を仮定）
                return {"message": "Price updated successfully"}

        raise HTTPException(status_code=404, detail="Product not found")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
