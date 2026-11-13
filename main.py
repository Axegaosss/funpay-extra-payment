
import os
import logging
import inspect

from fastapi import FastAPI, Header, HTTPException
from FunPayAPI import Account

app = FastAPI()

API_SECRET = os.getenv("API_SECRET")
FUNPAY_GOLDEN_KEY = os.getenv("FUNPAY_GOLDEN_KEY")

logging.basicConfig(level=logging.INFO)


def check_secret(x_api_secret):
    if not API_SECRET or x_api_secret != API_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_account():
    if not FUNPAY_GOLDEN_KEY:
        raise HTTPException(
            status_code=500,
            detail="FunPay key not configured"
        )
    try:
        return Account(FUNPAY_GOLDEN_KEY).get()
    except Exception:
        logging.exception("FunPay connection error")
        raise HTTPException(
            status_code=502,
            detail="FunPay connection failed"
        )


@app.get("/")
def home():
    return {
        "status": "FunPay Extra Payment запущен"
    }


@app.post("/check-funpay")
def check_funpay(x_api_secret: str = Header(None)):
    check_secret(x_api_secret)

    account = get_account()

    return {
        "status": "connected",
        "username": account.username
    }


@app.post("/inspect-template")
def inspect_template(x_api_secret: str = Header(None)):
    check_secret(x_api_secret)

    account = get_account()

    try:
        lot = account.get_lot_fields(82022625)

        return {
            "status": "success",
            "lot_id": 82022625,
            "node_id": lot.fields.get("node_id"),
            "title": lot.fields.get("fields[summary][ru]"),
            "price": lot.fields.get("price")
        }

    except Exception:
        logging.exception("FunPay template error")

        raise HTTPException(
            status_code=502,
            detail="Template inspection failed. Check Railway logs."
        )


@app.get("/methods")
def methods():
    return {
        "account_methods": [
            name for name in dir(Account)
            if not name.startswith("_")
        ]
    }


@app.get("/method-info")
def method_info():
    result = {}

    for name in ("get_lot_fields", "save_lot"):
        method = getattr(Account, name, None)

        if method:
            result[name] = str(inspect.signature(method))
        else:
            result[name] = "not available"

    return result


@app.get("/library-info")
def library_info():
    result = {}

    for name in ("get_lot_fields", "save_lot"):
        method = getattr(Account, name, None)

        if method:
            try:
                result[name] = inspect.getsource(method)
            except Exception:
                result[name] = "Source unavailable"
        else:
            result[name] = "Method unavailable"

    return result


@app.get("/lotfields-info")
def lotfields_info():
    try:
        cls = Account.get_lot_fields.__globals__["types"].LotFields

        return {
            "source": inspect.getsource(cls)
        }

    except Exception as e:
        logging.exception("LotFields inspection error")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/category-info")
def category_info():
    result = {}

    for name in (
        "get_category",
        "get_subcategory"
    ):
        method = getattr(Account, name, None)

        if method:
            try:
                result[name] = inspect.getsource(method)
            except Exception:
                result[name] = "Source unavailable"

    for name in ("categories", "subcategories"):
        prop = getattr(Account, name, None)

        if isinstance(prop, property) and prop.fget:
            try:
                result[name] = inspect.getsource(prop.fget)
            except Exception:
                result[name] = "Source unavailable"

    return result


@app.get("/category-class-info")
def category_class_info():
    try:
        from FunPayAPI import types

        return {
            "category": inspect.getsource(types.Category),
            "subcategory": inspect.getsource(types.SubCategory)
        }

    except Exception as e:
        logging.exception("Category inspection error")
        raise HTTPException(
            status_code=500,
            detail=str(e)
    )
