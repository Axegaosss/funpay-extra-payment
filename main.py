
import os
import logging
import inspect
import re
from decimal import Decimal, InvalidOperation

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
        raise HTTPException(status_code=500, detail="FunPay key not configured")

    try:
        return Account(FUNPAY_GOLDEN_KEY).get()
    except Exception:
        logging.exception("FunPay connection error")
        raise HTTPException(status_code=502, detail="FunPay connection failed")


def read_form(response):
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

        selected = field.find("option", selected=True) or field.find("option")
        if selected:
            fields[name] = selected.get("value", "")

    for field in form.find_all("input", {"type": "checkbox"}):
        if field.get("name") and field.has_attr("checked"):
            fields[field["name"]] = "on"

    return fields


def find_lot_link(data):
    if isinstance(data, dict):
        for key in ("url", "offer_url", "link"):
            value = data.get(key)
            if isinstance(value, str):
                match = re.search(r"(?:https?://funpay\.com)?/lots/offer\?id=(\d+)", value)
                if match:
                    return "https://funpay.com/lots/offer?id=" + match.group(1)

        for key in ("offer_id", "lot_id", "id"):
            value = data.get(key)
            if str(value).isdigit() and int(value) > 0:
                return "https://funpay.com/lots/offer?id=" + str(value)

        for value in data.values():
            result = find_lot_link(value)
            if result:
                return result

    elif isinstance(data, list):
        for value in data:
            result = find_lot_link(value)
            if result:
                return result

    elif isinstance(data, str):
        match = re.search(r"(?:https?://funpay\.com)?/lots/offer\?id=(\d+)", data)
        if match:
            return "https://funpay.com/lots/offer?id=" + match.group(1)

    return None


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

        fields = read_form(response)
        account.csrf_token = fields.get("csrf_token", account.csrf_token)

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
        logging.exception("Template inspection error")
        raise HTTPException(status_code=502, detail="Template inspection failed")


@app.post("/create-payment")
def create_payment(data: dict, x_api_secret: str = Header(None)):
    check_secret(x_api_secret)

    order_id = str(data.get("order_id", "")).strip()
    amount_raw = str(data.get("amount", "")).replace(",", ".").strip()

    if not order_id.isdigit():
        raise HTTPException(status_code=400, detail="Введите номер заказа")

    try:
        amount = Decimal(amount_raw)
        if not amount.is_finite() or amount <= 0:
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="Некорректная сумма")

    account = get_account()

    try:
        # Получаем форму СОЗДАНИЯ нового лота.
        response = account.method(
            "get",
            "lots/offerEdit?node=888",
            {},
            {},
            raise_not_200=True
        )

        fields = read_form(response)

        account.csrf_token = fields.get("csrf_token", account.csrf_token)

        # Важно: 0 означает новый лот.
        # Шаблон 82022625 не редактируется.
        fields["offer_id"] = "0"
        fields["node_id"] = "888"
        fields["csrf_token"] = account.csrf_token
        fields["price"] = str(amount)
        fields["amount"] = "1"
        fields["active"] = "on"

        title = f"Доплата к заказу #{order_id}"
        description = f"Дополнительная оплата к заказу #{order_id}"

        fields["fields[summary][ru]"] = title
        fields["fields[summary][en]"] = title
        fields["fields[desc][ru]"] = description
        fields["fields[desc][en]"] = description

        headers = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest"
        }

        result = account.method(
            "post",
            "lots/offerSave",
            headers,
            fields,
            raise_not_200=True
        )

        try:
            result_data = result.json()
        except Exception:
            logging.error("FunPay returned a non-JSON save response")
            raise HTTPException(
                status_code=502,
                detail="FunPay ответил не JSON. Проверь Railway Logs."
            )

        if result_data.get("error") or result_data.get("errors"):
            logging.error("FunPay save error: %s", result_data)
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "FunPay не сохранил лот",
                    "errors": result_data.get("errors"),
                    "error": result_data.get("error")
                }
            )

        link = find_lot_link(result_data)

        if not link:
            logging.info("FunPay save response keys: %s", list(result_data.keys()))
            return {
                "status": "saved",
                "message": "Ответ об успешном сохранении получен, но ID лота не найден.",
                "response": result_data
            }

        return {
            "status": "success",
            "order_id": order_id,
            "amount": str(amount),
            "url": link
        }

    except HTTPException:
        raise
    except Exception:
        logging.exception("Create payment error")
        raise HTTPException(
            status_code=502,
            detail="Не удалось создать лот. Проверь Railway Logs."
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
        result[name] = str(inspect.signature(method)) if method else "not available"

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
    
