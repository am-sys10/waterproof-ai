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
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 環境変数から credentials.json の内容を取得
credentials_json = os.getenv("GOOGLE_CREDENTIALS")
if credentials_json is None:
    raise ValueError("環境変数 GOOGLE_CREDENTIALS が設定されていません")

creds_dict = json.loads(credentials_json)

# Google Sheets API の認証設定
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

SHEET_ID = "1iVxcgSJbT4FoCr-322hbzjiNdsTkTJ8ZviG1dPKUgoU"

@app.get("/")
def root():
    return {"message": "Waterproof AI API is running!"}

@app.get("/get_price")
def get_price(product_id: str, customer_id: str = None, site_id: str = None):
    try:
        sheet_products = client.open_by_key(SHEET_ID).worksheet("products")
        products = sheet_products.get_all_records()
        company_price = None
        product_name = ""
        for rec in products:
            if rec.get("product_id") == product_id:
                company_price = rec.get("price")
                product_name = rec.get("product_name")
                break

        customer_price = None
        if customer_id:
            sheet_customer = client.open_by_key(SHEET_ID).worksheet("customer_prices")
            customer_records = sheet_customer.get_all_records()
            for rec in customer_records:
                if rec.get("product_id") == product_id and rec.get("customer_id") == customer_id:
                    customer_price = rec.get("price")
                    break

        site_price = None
        if site_id:
            sheet_site = client.open_by_key(SHEET_ID).worksheet("site_prices")
            site_records = sheet_site.get_all_records()
            for rec in site_records:
                if rec.get("product_id") == product_id and rec.get("site_id") == site_id:
                    site_price = rec.get("price")
                    break

        # 顧客名の取得
        customer_name = ""
        if customer_id:
            customer_master = client.open_by_key(SHEET_ID).worksheet("customer_master").get_all_records()
            for rec in customer_master:
                if rec.get("customer_id") == customer_id:
                    customer_name = rec.get("customer_name")
                    break

        # 現場名の取得
        site_name = ""
        if site_id:
            site_master = client.open_by_key(SHEET_ID).worksheet("site_master").get_all_records()
            for rec in site_master:
                if rec.get("site_id") == site_id:
                    site_name = rec.get("site_name")
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

        cheapest_source, cheapest_price = min(available_prices, key=lambda x: x[1])
        return {
            "product_id": product_id,
            "product_name": product_name,
            "lowest_price": cheapest_price,
            "source": cheapest_source,
            "details": {
                "company_price": company_price,
                "customer_price": customer_price,
                "site_price": site_price,
                "customer_name": customer_name,
                "site_name": site_name
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_price_all")
def get_price_all():
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
