import os
from fastapi import FastAPI, Header, HTTPException

app = FastAPI()

API_SECRET = os.getenv("API_SECRET")

@app.get("/")
def home():
    return {"status": "FunPay Extra Payment запущен"}

@app.post("/create-payment")
def create_payment(data: dict, x_api_secret: str = Header(None)):
    if not API_SECRET or x_api_secret != API_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    order_id = str(data.get("order_id", "")).strip()
    amount = data.get("amount")

    if not order_id or not isinstance(amount, (int, float)) or amount < 1:
        raise HTTPException(status_code=400, detail="Проверь номер заказа и сумму")

    return {"status": "test", "order_id": order_id, "amount": amount}
