
import os
import logging
import inspect
from fastapi import FastAPI, Header, HTTPException
from FunPayAPI import Account

app = FastAPI()

API_SECRET = os.getenv("API_SECRET")
FUNPAY_GOLDEN_KEY = os.getenv("FUNPAY_GOLDEN_KEY")


@app.get("/")
def home():
    return {"status": "FunPay Extra Payment запущен"}


def check_secret(x_api_secret):
    if not API_SECRET or x_api_secret != API_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/check-funpay")
def check_funpay(x_api_secret: str = Header(None)):
    check_secret(x_api_secret)

    if not FUNPAY_GOLDEN_KEY:
        raise HTTPException(status_code=500, detail="FunPay key not configured")

    try:
        account = Account(FUNPAY_GOLDEN_KEY).get()
        return {"status": "connected", "username": account.username}
    except Exception:
        logging.exception("FunPay connection error")
        raise HTTPException(status_code=502, detail="FunPay connection failed")


@app.post("/inspect-template")
def inspect_template(x_api_secret: str = Header(None)):
    check_secret(x_api_secret)

    if not FUNPAY_GOLDEN_KEY:
        raise HTTPException(status_code=500, detail="FunPay key not configured")

    try:
        account = Account(FUNPAY_GOLDEN_KEY).get()
        lot = account.get_lot_fields(82022625)

        return {
            "status": "success",
            "lot_id": 82022625,
            "fields": list(lot.fields.keys())
        }
    except Exception:
        logging.exception("FunPay template error")
        raise HTTPException(status_code=502, detail="Template inspection failed")


@app.get("/methods")
def methods():
    names = [
        name for name in dir(Account)
        if any(word in name.lower() for word in
               ["lot", "offer", "category", "fields"])
    ]
    return {"methods": names}


@app.get("/method-info")
def method_info():
    return {
        "get_lot_fields": str(inspect.signature(Account.get_lot_fields)),
        "save_lot": str(inspect.signature(Account.save_lot))
    }


@app.get("/library-info")
def library_info():
    return {
        "get_lot_fields": inspect.getsource(Account.get_lot_fields),
        "save_lot": inspect.getsource(Account.save_lot)
    }


@app.get("/lotfields-info")
def lotfields_info():
    cls = Account.get_lot_fields.__globals__["types"].LotFields
    return {"source": inspect.getsource(cls)}
        
