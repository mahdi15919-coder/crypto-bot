from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Any, Dict, List
import json
import random
import string
import requests

app = FastAPI(title="Crypto Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_FILE = "config.json"
ORDERS_FILE = "orders.json"
INVENTORY_FILE = "inventory.json"
PAYMENT_INFO_FILE = "payment_info.json"

BINANCE_BASE_URLS = [
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
]

ASSET_CODES = ["USDT", "TRX", "TON", "BNB"]


def load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_id(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def format_float(value: float, max_decimals: int = 8) -> str:
    s = f"{value:.{max_decimals}f}".rstrip("0").rstrip(".")
    return s if s else "0"


def get_usdt_buy_sell_prices(config: Dict[str, Any]) -> Dict[str, float]:
    manual = float(config["usdt_manual_price_irr"])
    buy_profit = float(config["my_profit_percent_buy"])
    sell_profit = float(config["my_profit_percent_sell"])

    sell_to_user = manual * (1 + sell_profit / 100)
    buy_from_user = manual * (1 - buy_profit / 100)

    return {
        "sell_to_user": sell_to_user,
        "buy_from_user": buy_from_user,
    }


def fetch_binance_symbol_price(symbol: str) -> float:
    last_error = None

    for base_url in BINANCE_BASE_URLS:
        try:
            response = requests.get(
                f"{base_url}/api/v3/ticker/price",
                params={"symbol": symbol},
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()

            if "price" not in data:
                raise ValueError(f"Unexpected Binance response: {data}")

            return float(data["price"])
        except Exception as e:
            last_error = e

    raise RuntimeError(f"خطا در دریافت قیمت از بایننس: {last_error}")


def get_asset_price_in_usdt(asset_code: str, side: str, config: Dict[str, Any]) -> float:
    if asset_code == "USDT":
        return 1.0

    symbol = config["assets"][asset_code]["binance_symbol"]
    base_price = fetch_binance_symbol_price(symbol)
    markup = float(config["binance_markup_percent"])

    if side == "buy":
        return base_price * (1 + markup / 100)

    return base_price * (1 - markup / 100)


def get_asset_price_in_irr(asset_code: str, side: str, config: Dict[str, Any]) -> float:
    if asset_code == "USDT":
        usdt_prices = get_usdt_buy_sell_prices(config)
        return usdt_prices["sell_to_user"] if side == "buy" else usdt_prices["buy_from_user"]

    usdt_manual = float(config["usdt_manual_price_irr"])
    buy_profit = float(config["my_profit_percent_buy"])
    sell_profit = float(config["my_profit_percent_sell"])

    base_irr = get_asset_price_in_usdt(asset_code, side, config) * usdt_manual

    if side == "buy":
        return base_irr * (1 + sell_profit / 100)

    return base_irr * (1 - buy_profit / 100)


def calculate_order(asset_code: str, network: str, amount: float, side: str, config: Dict[str, Any]) -> Dict[str, Any]:
    network_info = config["assets"][asset_code]["networks"][network]
    fee_asset = network_info["fee_asset"]
    fee_amount = float(network_info["fee_amount"])

    unit_price_usdt = get_asset_price_in_usdt(asset_code, side, config)
    unit_price_irr = get_asset_price_in_irr(asset_code, side, config)

    fee_asset_price_irr = get_asset_price_in_irr(fee_asset, side, config)
    fee_irr = fee_amount * fee_asset_price_irr

    subtotal = amount * unit_price_irr

    if side == "buy":
        total = subtotal + fee_irr
    else:
        total = subtotal - fee_irr

    return {
        "side": side,
        "asset_code": asset_code,
        "network": network,
        "amount": amount,
        "unit_price_usdt": unit_price_usdt,
        "unit_price_irr": unit_price_irr,
        "fee_asset": fee_asset,
        "fee_amount": fee_amount,
        "fee_irr": fee_irr,
        "subtotal_irr": subtotal,
        "total_irr": total,
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/summary")
def summary():
    config = load_json(CONFIG_FILE, {})
    inventory = load_json(INVENTORY_FILE, {})
    payment = load_json(PAYMENT_INFO_FILE, {"bank_accounts": [], "wallet_addresses": []})
    usdt = get_usdt_buy_sell_prices(config)

    return {
        "usdt_prices": usdt,
        "assets": ASSET_CODES,
        "inventory": inventory,
        "bank_count": len(payment["bank_accounts"]),
        "wallet_count": len(payment["wallet_addresses"]),
    }


@app.get("/orders")
def orders(user_id: int = Query(...)):
    all_orders: List[Dict[str, Any]] = load_json(ORDERS_FILE, [])
    return [o for o in all_orders if o.get("user_id") == user_id]


@app.get("/banks")
def banks():
    payment = load_json(PAYMENT_INFO_FILE, {"bank_accounts": [], "wallet_addresses": []})
    return payment["bank_accounts"]


@app.get("/wallets")
def wallets():
    payment = load_json(PAYMENT_INFO_FILE, {"bank_accounts": [], "wallet_addresses": []})
    return payment["wallet_addresses"]


@app.get("/networks")
def networks(asset_code: str = Query(...)):
    config = load_json(CONFIG_FILE, {})
    asset_code = asset_code.upper()

    if asset_code not in config["assets"]:
        raise HTTPException(status_code=404, detail="asset not found")

    return {
        "asset_code": asset_code,
        "networks": list(config["assets"][asset_code]["networks"].keys()),
    }


@app.post("/quote")
def quote(data: dict = Body(...)):
    config = load_json(CONFIG_FILE, {})
    inventory = load_json(INVENTORY_FILE, {})

    side = data.get("side")
    asset_code = str(data.get("asset_code", "")).upper()
    network = str(data.get("network", "")).upper()
    amount = float(data.get("amount", 0))

    if side not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="invalid side")

    if asset_code not in config["assets"]:
        raise HTTPException(status_code=400, detail="invalid asset")

    if network not in config["assets"][asset_code]["networks"]:
        raise HTTPException(status_code=400, detail="invalid network")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="invalid amount")

    result = calculate_order(asset_code, network, amount, side, config)

    if side == "buy":
        current_inventory = float(inventory.get(asset_code, 0))
        if amount > current_inventory:
            raise HTTPException(
                status_code=400,
                detail=f"موجودی کافی نیست. موجودی فعلی {asset_code}: {format_float(current_inventory)}"
            )

    return result


@app.post("/create-order")
def create_order(data: dict = Body(...)):
    config = load_json(CONFIG_FILE, {})
    inventory = load_json(INVENTORY_FILE, {})
    orders = load_json(ORDERS_FILE, [])

    user_id = int(data["user_id"])
    side = str(data["side"]).lower()
    asset_code = str(data["asset_code"]).upper()
    network = str(data["network"]).upper()
    amount = float(data["amount"])
    wallet_address = str(data.get("wallet_address", "")).strip()

    if side not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="invalid side")

    if asset_code not in config["assets"]:
        raise HTTPException(status_code=400, detail="invalid asset")

    if network not in config["assets"][asset_code]["networks"]:
        raise HTTPException(status_code=400, detail="invalid network")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="invalid amount")

    if not wallet_address:
        raise HTTPException(status_code=400, detail="wallet address required")

    result = calculate_order(asset_code, network, amount, side, config)

    if side == "buy":
        current_inventory = float(inventory.get(asset_code, 0))
        if amount > current_inventory:
            raise HTTPException(
                status_code=400,
                detail=f"موجودی کافی نیست. موجودی فعلی {asset_code}: {format_float(current_inventory)}"
            )

    order_id = generate_id()

    order = {
        "order_id": order_id,
        "user_id": user_id,
        "side": result["side"],
        "asset_code": result["asset_code"],
        "network": result["network"],
        "amount": result["amount"],
        "unit_price_irr": result["unit_price_irr"],
        "fee_amount": result["fee_amount"],
        "fee_asset": result["fee_asset"],
        "fee_irr": result["fee_irr"],
        "total_irr": result["total_irr"],
        "wallet_address": wallet_address,
        "selected_bank_id": None,
        "status": "pending",
        "receipt_file_id": None,
        "txid": None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    orders.append(order)
    save_json(ORDERS_FILE, orders)

    return {
        "ok": True,
        "order_id": order_id,
        "order": order,
    }


@app.get("/order/{order_id}")
def get_order(order_id: str):
    orders = load_json(ORDERS_FILE, [])
    for order in orders:
        if order.get("order_id") == order_id:
            return order
    raise HTTPException(status_code=404, detail="order not found")


@app.post("/order/{order_id}/select-bank")
def select_bank(order_id: str, data: dict = Body(...)):
    bank_id = str(data.get("bank_id", "")).strip()

    payment = load_json(PAYMENT_INFO_FILE, {"bank_accounts": [], "wallet_addresses": []})
    banks = payment["bank_accounts"]
    bank = next((b for b in banks if b["id"] == bank_id), None)

    if not bank:
        raise HTTPException(status_code=404, detail="bank not found")

    orders = load_json(ORDERS_FILE, [])
    for order in orders:
        if order.get("order_id") == order_id:
            order["selected_bank_id"] = bank_id
            order["status"] = "waiting_receipt"
            save_json(ORDERS_FILE, orders)
            return {
                "ok": True,
                "order_id": order_id,
                "bank": bank,
                "status": "waiting_receipt",
            }

    raise HTTPException(status_code=404, detail="order not found")


@app.get("/order/{order_id}/wallet")
def get_wallet_for_order(order_id: str):
    orders = load_json(ORDERS_FILE, [])
    payment = load_json(PAYMENT_INFO_FILE, {"bank_accounts": [], "wallet_addresses": []})

    order = next((o for o in orders if o.get("order_id") == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")

    wallet = next(
        (
            w for w in payment["wallet_addresses"]
            if w["asset_code"] == order["asset_code"] and w["network"] == order["network"]
        ),
        None
    )

    if not wallet:
        raise HTTPException(status_code=404, detail="wallet not found")

    return {
        "order_id": order_id,
        "wallet": wallet
    }


@app.get("/admin/summary")
def admin_summary(admin_id: int = Query(...)):
    if admin_id != 5869677184:
        raise HTTPException(status_code=403, detail="forbidden")

    orders = load_json(ORDERS_FILE, [])
    inventory = load_json(INVENTORY_FILE, {})
    payment = load_json(PAYMENT_INFO_FILE, {"bank_accounts": [], "wallet_addresses": []})

    pending = [o for o in orders if o.get("status") in ["pending", "waiting_bank_selection", "waiting_receipt", "wallet_sent", "receipt_submitted", "paid", "sent"]]

    return {
        "order_count": len(orders),
        "active_order_count": len(pending),
        "inventory": inventory,
        "bank_count": len(payment["bank_accounts"]),
        "wallet_count": len(payment["wallet_addresses"]),
    }


@app.get("/admin/orders")
def admin_orders(admin_id: int = Query(...)):
    if admin_id != 5869677184:
        raise HTTPException(status_code=403, detail="forbidden")

    orders = load_json(ORDERS_FILE, [])
    return list(reversed(orders))[:50]


@app.post("/admin/order/{order_id}/status")
def admin_change_order_status(order_id: str, data: dict = Body(...)):
    if int(data.get("admin_id", 0)) != 5869677184:
        raise HTTPException(status_code=403, detail="forbidden")

    new_status = str(data.get("status", "")).strip()
    allowed = {"approved", "waiting_bank_selection", "waiting_receipt", "paid", "wallet_sent", "sent", "done", "rejected"}

    if new_status not in allowed:
        raise HTTPException(status_code=400, detail="invalid status")

    orders = load_json(ORDERS_FILE, [])
    for order in orders:
        if order.get("order_id") == order_id:
            order["status"] = new_status
            save_json(ORDERS_FILE, orders)
            return {"ok": True, "order_id": order_id, "status": new_status}

    raise HTTPException(status_code=404, detail="order not found")