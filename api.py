from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json
import random
import string
import requests
import base64
import os

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
RECEIPTS_DIR = "receipts"

BINANCE_BASE_URLS = [
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
]

ASSET_CODES = ["USDT", "TRX", "TON", "BNB"]
ADMIN_ID = 5869677184

os.makedirs(RECEIPTS_DIR, exist_ok=True)
app.mount("/receipts", StaticFiles(directory=RECEIPTS_DIR), name="receipts")


# =========================================================
# helpers
# =========================================================

def load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ensure_admin(admin_id: int) -> None:
    if int(admin_id) != ADMIN_ID:
        raise HTTPException(status_code=403, detail="forbidden")


def generate_id(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def generate_prefixed_id(prefix: str, length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    return prefix + "".join(random.choices(chars, k=length))


def format_float(value: float, max_decimals: int = 8) -> str:
    s = f"{value:.{max_decimals}f}".rstrip("0").rstrip(".")
    return s if s else "0"


def load_orders() -> List[Dict[str, Any]]:
    return load_json(ORDERS_FILE, [])


def save_orders(data: List[Dict[str, Any]]) -> None:
    save_json(ORDERS_FILE, data)


def find_order_or_404(order_id: str) -> Dict[str, Any]:
    for order in load_orders():
        if order.get("order_id") == order_id:
            return order
    raise HTTPException(status_code=404, detail="order not found")


def update_order(order_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    orders = load_orders()
    for order in orders:
        if order.get("order_id") == order_id:
            order.update(updates)
            save_orders(orders)
            return order
    raise HTTPException(status_code=404, detail="order not found")


def get_payment_info() -> Dict[str, Any]:
    return load_json(PAYMENT_INFO_FILE, {"bank_accounts": [], "wallet_addresses": []})


def save_payment_info(data: Dict[str, Any]) -> None:
    save_json(PAYMENT_INFO_FILE, data)


def get_inventory() -> Dict[str, float]:
    return load_json(INVENTORY_FILE, {"USDT": 0, "TRX": 0, "TON": 0, "BNB": 0})


def save_inventory(data: Dict[str, float]) -> None:
    save_json(INVENTORY_FILE, data)


def get_config() -> Dict[str, Any]:
    return load_json(CONFIG_FILE, {})


def save_config(data: Dict[str, Any]) -> None:
    save_json(CONFIG_FILE, data)


def validate_user_order(order: Dict[str, Any], user_id: int) -> None:
    if int(order["user_id"]) != int(user_id):
        raise HTTPException(status_code=403, detail="not your order")


# =========================================================
# market pricing
# =========================================================

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


def fetch_nobitex_usdt_irr_best_effort() -> float:
    """
    Best-effort legacy call. اگر جواب نداد، fallback روی Wallex می‌رود.
    """
    url = "https://api.nobitex.ir/market/stats"
    candidates = [
        {"srcCurrency": "usdt", "dstCurrency": "rls"},
        {"srcCurrency": "usdt", "dstCurrency": "irt"},
    ]

    last_error = None
    for payload in candidates:
        try:
            response = requests.post(url, json=payload, timeout=6)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                last_error = data
                continue

            stats = data.get("stats", {})
            if isinstance(stats, dict):
                for _, market_data in stats.items():
                    if isinstance(market_data, dict):
                        for key in ["latest", "lastTradePrice", "bestSell"]:
                            if key in market_data:
                                return float(market_data[key])
            last_error = data
        except Exception as e:
            last_error = e

    raise RuntimeError(f"Nobitex failed: {last_error}")


def fetch_wallex_usdt_irr() -> float:
    url = "https://api.wallex.ir/v1/otc/markets"
    response = requests.get(url, timeout=6)
    response.raise_for_status()
    data = response.json()

    if not data.get("success"):
        raise RuntimeError(f"Wallex failed: {data}")

    symbols = data.get("result", {}).get("symbols", {})
    for symbol in ["USDTTMN", "USDTTMN", "USDTIRT"]:
        if symbol in symbols:
            stats = symbols[symbol].get("stats", {})
            if "lastPrice" in stats:
                return float(stats["lastPrice"])

    raise RuntimeError("Wallex USDT TMN market not found")


def get_live_or_manual_usdt_irr(config: Dict[str, Any]) -> float:
    mode = config.get("usdt_price_mode", "manual")
    source = config.get("usdt_exchange_source", "auto")

    if mode == "manual":
        return float(config["usdt_manual_price_irr"])

    errors = []

    def update_cache(price: float) -> float:
        config["usdt_cached_price_irr"] = price
        config["usdt_cached_at"] = datetime.utcnow().isoformat()
        save_config(config)
        return price

    if source in ["auto", "nobitex"]:
        try:
            return update_cache(fetch_nobitex_usdt_irr_best_effort())
        except Exception as e:
            errors.append(f"nobitex: {e}")

    if source in ["auto", "wallex"]:
        try:
            return update_cache(fetch_wallex_usdt_irr())
        except Exception as e:
            errors.append(f"wallex: {e}")

    cached_price = config.get("usdt_cached_price_irr")
    cached_at = config.get("usdt_cached_at")
    if cached_price and cached_at:
        try:
            dt = datetime.fromisoformat(cached_at)
            if datetime.utcnow() - dt <= timedelta(minutes=10):
                return float(cached_price)
        except Exception:
            pass

    raise RuntimeError("دریافت نرخ تتر ناموفق بود و کش معتبر هم وجود ندارد")


def get_usdt_buy_sell_prices(config: Dict[str, Any]) -> Dict[str, float]:
    base_price = float(get_live_or_manual_usdt_irr(config))
    buy_profit = float(config["my_profit_percent_buy"])
    sell_profit = float(config["my_profit_percent_sell"])

    sell_to_user = base_price * (1 + sell_profit / 100)
    buy_from_user = base_price * (1 - buy_profit / 100)

    return {
        "sell_to_user": sell_to_user,
        "buy_from_user": buy_from_user,
        "base_price": base_price,
    }


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

    usdt_base = float(get_live_or_manual_usdt_irr(config))
    buy_profit = float(config["my_profit_percent_buy"])
    sell_profit = float(config["my_profit_percent_sell"])

    base_irr = get_asset_price_in_usdt(asset_code, side, config) * usdt_base

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


# =========================================================
# user endpoints
# =========================================================

@app.get("/health")
def health():
    return {"ok": True}


@app.get("/summary")
def summary():
    config = get_config()
    inventory = get_inventory()
    payment = get_payment_info()
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
    return [o for o in load_orders() if int(o.get("user_id")) == int(user_id)]


@app.get("/banks")
def banks():
    return get_payment_info()["bank_accounts"]


@app.get("/wallets")
def wallets():
    return get_payment_info()["wallet_addresses"]


@app.get("/networks")
def networks(asset_code: str = Query(...)):
    config = get_config()
    asset_code = asset_code.upper()

    if asset_code not in config["assets"]:
        raise HTTPException(status_code=404, detail="asset not found")

    return {
        "asset_code": asset_code,
        "networks": list(config["assets"][asset_code]["networks"].keys()),
    }


@app.post("/quote")
def quote(data: dict = Body(...)):
    config = get_config()
    inventory = get_inventory()

    side = str(data.get("side", "")).lower()
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
    config = get_config()
    inventory = get_inventory()
    orders = load_orders()

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
        "status": "pending_admin",
        "receipt_file_id": None,
        "receipt_url": None,
        "txid": None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    orders.append(order)
    save_orders(orders)

    return {"ok": True, "order": order}


@app.get("/order/{order_id}")
def get_order(order_id: str):
    return find_order_or_404(order_id)


@app.post("/order/{order_id}/select-bank")
def select_bank(order_id: str, data: dict = Body(...)):
    user_id = int(data.get("user_id", 0))
    bank_id = str(data.get("bank_id", "")).strip()

    order = find_order_or_404(order_id)
    validate_user_order(order, user_id)

    if order["status"] != "waiting_bank":
        raise HTTPException(status_code=400, detail="invalid order step")

    banks = get_payment_info()["bank_accounts"]
    bank = next((b for b in banks if b["id"] == bank_id), None)
    if not bank:
        raise HTTPException(status_code=404, detail="bank not found")

    updated = update_order(order_id, {
        "selected_bank_id": bank_id,
        "status": "waiting_receipt",
    })

    return {"ok": True, "order": updated, "bank": bank}


@app.get("/order/{order_id}/wallet")
def get_wallet_for_order(order_id: str):
    order = find_order_or_404(order_id)
    payment = get_payment_info()

    wallet = next(
        (
            w for w in payment["wallet_addresses"]
            if w["asset_code"] == order["asset_code"] and w["network"] == order["network"]
        ),
        None
    )
    if not wallet:
        raise HTTPException(status_code=404, detail="wallet not found")

    return {"ok": True, "wallet": wallet}


@app.post("/order/{order_id}/upload-receipt")
def upload_receipt(order_id: str, data: dict = Body(...)):
    user_id = int(data.get("user_id", 0))
    image_base64 = str(data.get("image_base64", "")).strip()

    order = find_order_or_404(order_id)
    validate_user_order(order, user_id)

    if order["status"] != "waiting_receipt":
        raise HTTPException(status_code=400, detail="invalid order step")

    if not image_base64:
        raise HTTPException(status_code=400, detail="image_base64 required")

    try:
        raw = image_base64.split(",", 1)[-1]
        file_bytes = base64.b64decode(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid base64 image")

    file_name = f"{order_id}.jpg"
    file_path = os.path.join(RECEIPTS_DIR, file_name)

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    updated = update_order(order_id, {
        "receipt_file_id": file_name,
        "receipt_url": f"/receipts/{file_name}",
        "status": "receipt_submitted",
    })

    return {"ok": True, "order": updated}


@app.post("/order/{order_id}/submit-txid")
def submit_txid(order_id: str, data: dict = Body(...)):
    user_id = int(data.get("user_id", 0))
    txid = str(data.get("txid", "")).strip()

    order = find_order_or_404(order_id)
    validate_user_order(order, user_id)

    if order["status"] not in ["wallet_ready", "waiting_txid"]:
        raise HTTPException(status_code=400, detail="invalid order step")
    if not txid:
        raise HTTPException(status_code=400, detail="txid required")

    updated = update_order(order_id, {
        "txid": txid,
        "status": "txid_submitted",
    })

    return {"ok": True, "order": updated}


# =========================================================
# admin endpoints
# =========================================================

@app.get("/admin/dashboard")
def admin_dashboard(admin_id: int = Query(...)):
    ensure_admin(admin_id)

    orders = load_orders()
    inventory = get_inventory()
    payment = get_payment_info()
    config = get_config()

    active_statuses = {
        "pending_admin", "waiting_bank", "waiting_receipt",
        "receipt_submitted", "wallet_ready", "waiting_txid",
        "txid_submitted", "paid", "sent"
    }

    active_orders = [o for o in orders if o.get("status") in active_statuses]
    done_orders = [o for o in orders if o.get("status") == "done"]

    buy_total = 0.0
    sell_total = 0.0
    for order in done_orders:
        if order["side"] == "buy":
            buy_total += float(order["total_irr"])
        else:
            sell_total += float(order["total_irr"])

    return {
        "order_count": len(orders),
        "active_order_count": len(active_orders),
        "done_order_count": len(done_orders),
        "buy_total_irr": buy_total,
        "sell_total_irr": sell_total,
        "inventory": inventory,
        "bank_count": len(payment["bank_accounts"]),
        "wallet_count": len(payment["wallet_addresses"]),
        "config": {
            "usdt_price_mode": config.get("usdt_price_mode", "manual"),
            "usdt_exchange_source": config.get("usdt_exchange_source", "auto"),
            "usdt_manual_price_irr": config.get("usdt_manual_price_irr"),
            "usdt_cached_price_irr": config.get("usdt_cached_price_irr"),
            "usdt_cached_at": config.get("usdt_cached_at"),
            "my_profit_percent_buy": config.get("my_profit_percent_buy"),
            "my_profit_percent_sell": config.get("my_profit_percent_sell"),
            "binance_markup_percent": config.get("binance_markup_percent"),
        }
    }


@app.get("/admin/orders")
def admin_orders(
    admin_id: int = Query(...),
    status: Optional[str] = Query(default=None),
    order_id: Optional[str] = Query(default=None),
):
    ensure_admin(admin_id)
    result = list(reversed(load_orders()))

    if status:
        result = [o for o in result if o.get("status") == status]

    if order_id:
        q = order_id.strip().upper()
        result = [o for o in result if q in str(o.get("order_id", "")).upper()]

    return result[:100]


@app.post("/admin/order/{order_id}/approve")
def admin_approve(order_id: str, data: dict = Body(...)):
    ensure_admin(int(data.get("admin_id", 0)))
    order = find_order_or_404(order_id)

    if order["status"] != "pending_admin":
        raise HTTPException(status_code=400, detail="invalid order step")

    if order["side"] == "buy":
        updated = update_order(order_id, {"status": "waiting_bank"})
    else:
        updated = update_order(order_id, {"status": "wallet_ready"})

    return {"ok": True, "order": updated}


@app.post("/admin/order/{order_id}/status")
def admin_change_order_status(order_id: str, data: dict = Body(...)):
    ensure_admin(int(data.get("admin_id", 0)))

    new_status = str(data.get("status", "")).strip()
    allowed = {"paid", "sent", "done", "rejected", "waiting_txid"}

    if new_status not in allowed:
        raise HTTPException(status_code=400, detail="invalid status")

    order = find_order_or_404(order_id)
    inventory = get_inventory()

    if new_status == "paid":
        if order["side"] == "buy" and order["status"] != "receipt_submitted":
            raise HTTPException(status_code=400, detail="invalid buy transition")
        if order["side"] == "sell" and order["status"] != "txid_submitted":
            raise HTTPException(status_code=400, detail="invalid sell transition")

    if new_status == "sent":
        if order["side"] != "buy" or order["status"] != "paid":
            raise HTTPException(status_code=400, detail="invalid transition")

    if new_status == "done":
        if order["status"] not in ["sent", "paid"]:
            raise HTTPException(status_code=400, detail="invalid transition")

        asset = order["asset_code"]
        amount = float(order["amount"])

        if order["side"] == "buy":
            current = float(inventory.get(asset, 0))
            if amount > current:
                raise HTTPException(status_code=400, detail=f"موجودی کافی برای {asset} نیست")
            inventory[asset] = current - amount
        else:
            inventory[asset] = float(inventory.get(asset, 0)) + amount

        save_inventory(inventory)

    updated = update_order(order_id, {"status": new_status})
    return {"ok": True, "order": updated}


@app.post("/admin/order/{order_id}/txid")
def admin_set_txid(order_id: str, data: dict = Body(...)):
    ensure_admin(int(data.get("admin_id", 0)))
    txid = str(data.get("txid", "")).strip()
    if not txid:
        raise HTTPException(status_code=400, detail="txid required")

    updated = update_order(order_id, {"txid": txid})
    return {"ok": True, "order": updated}


@app.get("/admin/inventory")
def admin_inventory(admin_id: int = Query(...)):
    ensure_admin(admin_id)
    return get_inventory()


@app.post("/admin/inventory/set")
def admin_inventory_set(data: dict = Body(...)):
    ensure_admin(int(data.get("admin_id", 0)))
    asset_code = str(data.get("asset_code", "")).upper()
    amount = float(data.get("amount", 0))

    if asset_code not in ASSET_CODES:
        raise HTTPException(status_code=400, detail="invalid asset")
    if amount < 0:
        raise HTTPException(status_code=400, detail="amount cannot be negative")

    inventory = get_inventory()
    inventory[asset_code] = amount
    save_inventory(inventory)
    return {"ok": True, "inventory": inventory}


@app.post("/admin/inventory/add")
def admin_inventory_add(data: dict = Body(...)):
    ensure_admin(int(data.get("admin_id", 0)))
    asset_code = str(data.get("asset_code", "")).upper()
    amount = float(data.get("amount", 0))

    if asset_code not in ASSET_CODES:
        raise HTTPException(status_code=400, detail="invalid asset")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")

    inventory = get_inventory()
    inventory[asset_code] = float(inventory.get(asset_code, 0)) + amount
    save_inventory(inventory)
    return {"ok": True, "inventory": inventory}


@app.post("/admin/inventory/remove")
def admin_inventory_remove(data: dict = Body(...)):
    ensure_admin(int(data.get("admin_id", 0)))
    asset_code = str(data.get("asset_code", "")).upper()
    amount = float(data.get("amount", 0))

    if asset_code not in ASSET_CODES:
        raise HTTPException(status_code=400, detail="invalid asset")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")

    inventory = get_inventory()
    current = float(inventory.get(asset_code, 0))
    if amount > current:
        raise HTTPException(status_code=400, detail="موجودی کافی نیست")

    inventory[asset_code] = current - amount
    save_inventory(inventory)
    return {"ok": True, "inventory": inventory}


@app.get("/admin/config")
def admin_get_config(admin_id: int = Query(...)):
    ensure_admin(admin_id)
    config = get_config()
    return {
        "usdt_price_mode": config.get("usdt_price_mode", "manual"),
        "usdt_exchange_source": config.get("usdt_exchange_source", "auto"),
        "usdt_manual_price_irr": config.get("usdt_manual_price_irr"),
        "usdt_cached_price_irr": config.get("usdt_cached_price_irr"),
        "usdt_cached_at": config.get("usdt_cached_at"),
        "my_profit_percent_buy": config.get("my_profit_percent_buy"),
        "my_profit_percent_sell": config.get("my_profit_percent_sell"),
        "binance_markup_percent": config.get("binance_markup_percent"),
        "assets": config.get("assets", {}),
    }


@app.post("/admin/config/update")
def admin_update_config(data: dict = Body(...)):
    ensure_admin(int(data.get("admin_id", 0)))
    config = get_config()

    if "usdt_price_mode" in data:
        mode = str(data["usdt_price_mode"]).strip()
        if mode not in ["manual", "exchange"]:
            raise HTTPException(status_code=400, detail="invalid usdt_price_mode")
        config["usdt_price_mode"] = mode

    if "usdt_exchange_source" in data:
        source = str(data["usdt_exchange_source"]).strip()
        if source not in ["auto", "nobitex", "wallex"]:
            raise HTTPException(status_code=400, detail="invalid usdt_exchange_source")
        config["usdt_exchange_source"] = source

    if "usdt_manual_price_irr" in data:
        config["usdt_manual_price_irr"] = float(data["usdt_manual_price_irr"])
    if "my_profit_percent_buy" in data:
        config["my_profit_percent_buy"] = float(data["my_profit_percent_buy"])
    if "my_profit_percent_sell" in data:
        config["my_profit_percent_sell"] = float(data["my_profit_percent_sell"])
    if "binance_markup_percent" in data:
        config["binance_markup_percent"] = float(data["binance_markup_percent"])

    save_config(config)
    return {"ok": True, "config": config}


@app.get("/admin/banks")
def admin_get_banks(admin_id: int = Query(...)):
    ensure_admin(admin_id)
    return get_payment_info()["bank_accounts"]


@app.post("/admin/banks/add")
def admin_add_bank(data: dict = Body(...)):
    ensure_admin(int(data.get("admin_id", 0)))

    bank_name = str(data.get("bank_name", "")).strip()
    account_number = str(data.get("account_number", "")).strip()
    sheba = str(data.get("sheba", "")).strip()
    card_number = str(data.get("card_number", "")).strip()
    owner_name = str(data.get("owner_name", "")).strip()

    if not all([bank_name, account_number, sheba, card_number, owner_name]):
        raise HTTPException(status_code=400, detail="all fields are required")

    payment = get_payment_info()
    bank = {
        "id": generate_prefixed_id("BANK_"),
        "bank_name": bank_name,
        "account_number": account_number,
        "sheba": sheba,
        "card_number": card_number,
        "owner_name": owner_name,
    }
    payment["bank_accounts"].append(bank)
    save_payment_info(payment)
    return {"ok": True, "bank": bank}


@app.post("/admin/banks/delete")
def admin_delete_bank(data: dict = Body(...)):
    ensure_admin(int(data.get("admin_id", 0)))
    bank_id = str(data.get("bank_id", "")).strip()

    payment = get_payment_info()
    old_len = len(payment["bank_accounts"])
    payment["bank_accounts"] = [b for b in payment["bank_accounts"] if b["id"] != bank_id]
    save_payment_info(payment)
    return {"ok": len(payment["bank_accounts"]) != old_len}


@app.get("/admin/wallets")
def admin_get_wallets(admin_id: int = Query(...)):
    ensure_admin(admin_id)
    return get_payment_info()["wallet_addresses"]


@app.post("/admin/wallets/add")
def admin_add_wallet(data: dict = Body(...)):
    ensure_admin(int(data.get("admin_id", 0)))

    asset_code = str(data.get("asset_code", "")).upper()
    network = str(data.get("network", "")).upper()
    address = str(data.get("address", "")).strip()

    if asset_code not in ASSET_CODES:
        raise HTTPException(status_code=400, detail="invalid asset")
    if not network or not address:
        raise HTTPException(status_code=400, detail="network and address are required")

    payment = get_payment_info()
    wallet = {
        "id": generate_prefixed_id("WALLET_"),
        "asset_code": asset_code,
        "network": network,
        "address": address,
    }
    payment["wallet_addresses"].append(wallet)
    save_payment_info(payment)
    return {"ok": True, "wallet": wallet}


@app.post("/admin/wallets/delete")
def admin_delete_wallet(data: dict = Body(...)):
    ensure_admin(int(data.get("admin_id", 0)))
    wallet_id = str(data.get("wallet_id", "")).strip()

    payment = get_payment_info()
    old_len = len(payment["wallet_addresses"])
    payment["wallet_addresses"] = [w for w in payment["wallet_addresses"] if w["id"] != wallet_id]
    save_payment_info(payment)
    return {"ok": len(payment["wallet_addresses"]) != old_len}


@app.get("/admin/networks")
def admin_get_networks(admin_id: int = Query(...)):
    ensure_admin(admin_id)
    return get_config()["assets"]


@app.post("/admin/networks/add")
def admin_add_network(data: dict = Body(...)):
    ensure_admin(int(data.get("admin_id", 0)))

    asset_code = str(data.get("asset_code", "")).upper()
    network = str(data.get("network", "")).upper()
    fee_asset = str(data.get("fee_asset", "")).upper()
    fee_amount = float(data.get("fee_amount", 0))

    config = get_config()

    if asset_code not in config["assets"]:
        raise HTTPException(status_code=400, detail="invalid asset")
    if fee_asset not in ASSET_CODES:
        raise HTTPException(status_code=400, detail="invalid fee_asset")
    if not network:
        raise HTTPException(status_code=400, detail="network required")
    if fee_amount < 0:
        raise HTTPException(status_code=400, detail="invalid fee_amount")
    if network in config["assets"][asset_code]["networks"]:
        raise HTTPException(status_code=400, detail="network already exists")

    config["assets"][asset_code]["networks"][network] = {
        "fee_asset": fee_asset,
        "fee_amount": fee_amount,
    }
    save_config(config)
    return {"ok": True, "assets": config["assets"]}


@app.post("/admin/networks/delete")
def admin_delete_network(data: dict = Body(...)):
    ensure_admin(int(data.get("admin_id", 0)))

    asset_code = str(data.get("asset_code", "")).upper()
    network = str(data.get("network", "")).upper()

    config = get_config()

    if asset_code not in config["assets"]:
        raise HTTPException(status_code=400, detail="invalid asset")
    if network not in config["assets"][asset_code]["networks"]:
        raise HTTPException(status_code=404, detail="network not found")
    if len(config["assets"][asset_code]["networks"]) <= 1:
        raise HTTPException(status_code=400, detail="آخرین شبکه را نمی‌شود حذف کرد")

    del config["assets"][asset_code]["networks"][network]
    save_config(config)
    return {"ok": True, "assets": config["assets"]}