
import os
import logging
import inspect

from fastapi import FastAPI, Header, HTTPException
from FunPayAPI import Account
from bs4 import BeautifulSoup

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
    return {"status": "FunPay Extra Payment запущен"}


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
        response = account.method(
            "get",
            "lots/offerEdit?offer=82022625",
            {},
            {},
            raise_not_200=True
        )

        soup = BeautifulSoup(response.content, "lxml")
        form = soup.find("form", class_="form-offer-editor")

        if not form:
            error = soup.find("p", class_="lead")
            message = error.get_text(strip=True) if error else "Offer form not found"
            raise HTTPException(status_code=502, detail=message)

        fields = {}

        for field in form.find_all("input"):
            name = field.get("name")
            if name and name != "query":
                fields[name] = field.get("value") or ""

        for field in form.find_all("textarea"):
            name = field.get("name")
            if name:
                fields[name] = field.get_text() or ""

        for field in form.find_all("select"):
            name = field.get("name")
            if not name:
                continue

            parent = field.find_parent(class_="form-group")
            if parent and "hidden" in parent.get("class", []):
                continue

            selected = field.find("option", selected=True)
            if selected:
                fields[name] = selected.get("value", "")

        for field in form.find_all("input", {"type": "checkbox"}):
            if field.get("name") and field.has_attr("checked"):
                fields[field["name"]] = "on"

        account.csrf_token = fields.get(
            "csrf_token",
            account.csrf_token
        )

        return {
            "status": "success",
            "lot_id": 82022625,
            "node_id": fields.get("node_id"),
            "title": fields.get("fields[summary][ru]"),
            "price": fields.get("price")
        }

    except HTTPException:
        raise
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

    for name in ("get_lot_fields", "save_lot", "save_offer", "method"):
        method = getattr(Account, name, None)
        result[name] = (
            str(inspect.signature(method))
            if method else "not available"
        )

    return result


@app.get("/library-info")
def library_info():
    result = {}

    for name in ("get_lot_fields", "save_lot", "save_offer"):
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
        return {"source": inspect.getsource(cls)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/category-info")
def category_info():
    result = {}

    for name in ("get_category", "get_subcategory"):
        method = getattr(Account, name, None)
        if method:
            result[name] = inspect.getsource(method)

    for name in ("categories", "subcategories"):
        prop = getattr(Account, name, None)
        if isinstance(prop, property) and prop.fget:
            result[name] = inspect.getsource(prop.fget)

    return result


@app.get("/category-class-info")
def category_class_info():
    from FunPayAPI import types

    return {
        "category": inspect.getsource(types.Category),
        "subcategory": inspect.getsource(types.SubCategory)
            }
    
