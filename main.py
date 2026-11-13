
import os
from fastapi import FastAPI, Header, HTTPException
from FunPayAPI import Account

app = FastAPI()

API_SECRET = os.getenv("API_SECRET")
FUNPAY_GOLDEN_KEY = os.getenv("FUNPAY_GOLDEN_KEY")

@app.get("/")
def home():
    return {"status": "FunPay Extra Payment запущен"}

@app.post("/check-funpay")
def check_funpay(x_api_secret: str = Header(None)):
    if not API_SECRET or x_api_secret != API_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not FUNPAY_GOLDEN_KEY:
        raise HTTPException(status_code=500, detail="FunPay key not configured")

    try:
        account = Account(FUNPAY_GOLDEN_KEY).get()
        return {
            "status": "connected",
            "username": account.username
        }
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="FunPay connection failed"
        )
    
@app.post("/inspect-template")
def inspect_template(x_api_secret: str = Header(None)):
    if not API_SECRET or x_api_secret != API_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        account = Account(FUNPAY_GOLDEN_KEY).get()
        lot = account.get_lot_fields(82022625)

        return {
            "status": "success",
            "lot_id": 82022625,
            "subcategory_id": lot.subcategory.id,
            "field_names": list(lot.fields.keys())
        }
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Не удалось прочитать шаблон"
        )
        
        
