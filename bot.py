import os
import json
import base64
import requests
from typing import Any, Dict, List

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    MenuButtonWebApp,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = "6651322898:AAHMYTqY7S38AmaygN7EgZwWz2yQCvdz3ig"
API_BASE = os.getenv("API_BASE", "https://crypto-bot-api-atmh.onrender.com")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://crypto-bot-three-ruby.vercel.app/index.html")
ADMIN_ID = 5869677184

user_state: Dict[int, Dict[str, Any]] = {}


def api_get(path: str, params: Dict[str, Any] | None = None) -> Any:
    r = requests.get(f"{API_BASE}{path}", params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def api_post(path: str, payload: Dict[str, Any]) -> Any:
    r = requests.post(f"{API_BASE}{path}", json=payload, timeout=30)
    if not r.ok:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(detail)
    return r.json()


def fmt_irr(v: float) -> str:
    return f"{int(round(v)):,}"


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 ورود به پنل", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💵 قیمت تتر", callback_data="menu_price")],
        [InlineKeyboardButton("📦 سفارش‌های من", callback_data="menu_orders")],
        [InlineKeyboardButton("🛠 پنل ادمین", callback_data="menu_admin")],
    ])


def order_user_actions(order: Dict[str, Any]) -> InlineKeyboardMarkup | None:
    oid = order["order_id"]
    st = order["status"]

    if st == "waiting_bank":
        return InlineKeyboardMarkup([[InlineKeyboardButton("🏦 انتخاب بانک", callback_data=f"user_banks_{oid}")]])
    if st == "waiting_receipt":
        return InlineKeyboardMarkup([[InlineKeyboardButton("📤 ارسال رسید", callback_data=f"user_receipt_{oid}")]])
    if st in ["wallet_ready", "waiting_txid"]:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("👛 نمایش ولت", callback_data=f"user_wallet_{oid}")],
            [InlineKeyboardButton("🔗 ثبت TXID", callback_data=f"user_txid_{oid}")]
        ])
    return None


def admin_order_actions(order: Dict[str, Any]) -> InlineKeyboardMarkup:
    oid = order["order_id"]
    st = order["status"]
    rows = []

    if st == "pending_admin":
        rows.append([
            InlineKeyboardButton("✅ تأیید", callback_data=f"admin_approve_{oid}"),
            InlineKeyboardButton("❌ رد", callback_data=f"admin_status_{oid}_rejected"),
        ])
    if st == "receipt_submitted":
        rows.append([
            InlineKeyboardButton("💰 تأیید پرداخت", callback_data=f"admin_status_{oid}_paid"),
            InlineKeyboardButton("❌ رد", callback_data=f"admin_status_{oid}_rejected"),
        ])
    if st == "txid_submitted":
        rows.append([
            InlineKeyboardButton("💰 تأیید واریز رمزارز", callback_data=f"admin_status_{oid}_paid"),
            InlineKeyboardButton("❌ رد", callback_data=f"admin_status_{oid}_rejected"),
        ])
    if st == "paid" and order["side"] == "buy":
        rows.append([InlineKeyboardButton("🚀 ارز ارسال شد", callback_data=f"admin_status_{oid}_sent")])
    if st in ["paid", "sent"] or (st == "paid" and order["side"] == "sell"):
        rows.append([InlineKeyboardButton("🏁 تکمیل", callback_data=f"admin_status_{oid}_done")])

    return InlineKeyboardMarkup(rows) if rows else InlineKeyboardMarkup([[InlineKeyboardButton("🔄 تازه‌سازی", callback_data="menu_admin")]])


def render_order(order: Dict[str, Any]) -> str:
    side = "خرید" if order["side"] == "buy" else "فروش"
    step_text = {
        "pending_admin": "⏳ منتظر تأیید ادمین",
        "waiting_bank": "🏦 منتظر انتخاب بانک",
        "waiting_receipt": "📤 منتظر ارسال رسید",
        "receipt_submitted": "📨 رسید ثبت شد، منتظر بررسی",
        "wallet_ready": "👛 ولت آماده است",
        "waiting_txid": "🔗 منتظر TXID",
        "txid_submitted": "📨 TXID ثبت شد، منتظر بررسی",
        "paid": "💰 تأیید شد",
        "sent": "🚀 ارسال شد",
        "done": "✅ تکمیل شد",
        "rejected": "❌ رد شد",
    }.get(order["status"], order["status"])

    txt = (
        f"📦 سفارش {order['order_id']}\n\n"
        f"نوع: {side}\n"
        f"ارز: {order['asset_code']}\n"
        f"شبکه: {order['network']}\n"
        f"مقدار: {order['amount']}\n"
        f"مبلغ: {fmt_irr(float(order['total_irr']))} ریال\n"
        f"وضعیت: {step_text}"
    )

    if order.get("txid"):
        txt += f"\nTXID: {order['txid']}"
    if order.get("receipt_url"):
        txt += "\nرسید: دارد"

    return txt


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.set_chat_menu_button(
        chat_id=update.effective_chat.id,
        menu_button=MenuButtonWebApp(
            text="پنل",
            web_app=WebAppInfo(url=WEBAPP_URL),
        ),
    )
    await update.message.reply_text(
        "سلام 👋\n\n"
        "همه مراحل اصلی خرید و فروش داخل Mini App و همین ربات با هم هماهنگ هستند.\n"
        "از دکمه‌ها استفاده کن:",
        reply_markup=start_keyboard(),
    )


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = api_get("/summary")
    usdt = data["usdt_prices"]
    await update.message.reply_text(
        f"💵 قیمت تتر\n\n"
        f"🟢 فروش به شما: {fmt_irr(usdt['sell_to_user'])} ریال\n"
        f"🔴 خرید از شما: {fmt_irr(usdt['buy_from_user'])} ریال"
    )


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    orders = api_get("/orders", {"user_id": user_id})

    if not orders:
        await update.message.reply_text("📭 هنوز سفارشی نداری")
        return

    for order in reversed(orders[-10:]):
        await update.message.reply_text(
            render_order(order),
            reply_markup=order_user_actions(order)
        )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ دسترسی نداری")
        return

    dash = api_get("/admin/dashboard", {"admin_id": ADMIN_ID})
    await update.message.reply_text(
        f"🛠 پنل ادمین\n\n"
        f"کل سفارش‌ها: {dash['order_count']}\n"
        f"سفارش‌های فعال: {dash['active_order_count']}\n"
        f"سفارش‌های done: {dash['done_order_count']}\n\n"
        f"USDT: {dash['inventory'].get('USDT', 0)}\n"
        f"TRX: {dash['inventory'].get('TRX', 0)}\n"
        f"TON: {dash['inventory'].get('TON', 0)}\n"
        f"BNB: {dash['inventory'].get('BNB', 0)}"
    )

    orders = api_get("/admin/orders", {"admin_id": ADMIN_ID})
    for order in orders[:10]:
        await update.message.reply_text(
            render_order(order),
            reply_markup=admin_order_actions(order)
        )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    try:
        if data == "menu_price":
            usdt = api_get("/summary")["usdt_prices"]
            await query.message.reply_text(
                f"💵 قیمت تتر\n\n"
                f"🟢 فروش به شما: {fmt_irr(usdt['sell_to_user'])} ریال\n"
                f"🔴 خرید از شما: {fmt_irr(usdt['buy_from_user'])} ریال"
            )
            return

        if data == "menu_orders":
            orders = api_get("/orders", {"user_id": uid})
            if not orders:
                await query.message.reply_text("📭 هنوز سفارشی نداری")
                return
            for order in reversed(orders[-10:]):
                await query.message.reply_text(render_order(order), reply_markup=order_user_actions(order))
            return

        if data == "menu_admin":
            if uid != ADMIN_ID:
                await query.message.reply_text("❌ دسترسی نداری")
                return
            orders = api_get("/admin/orders", {"admin_id": ADMIN_ID})
            for order in orders[:10]:
                await query.message.reply_text(render_order(order), reply_markup=admin_order_actions(order))
            return

        if data.startswith("user_banks_"):
            order_id = data.replace("user_banks_", "", 1)
            banks = api_get("/banks")
            if not banks:
                await query.message.reply_text("⚠️ هیچ حساب بانکی ثبت نشده")
                return

            buttons = []
            for bank in banks:
                buttons.append([InlineKeyboardButton(
                    f"{bank['bank_name']} | {bank['owner_name']}",
                    callback_data=f"user_banksel_{order_id}_{bank['id']}"
                )])
            await query.message.reply_text("🏦 یکی از حساب‌ها را انتخاب کن:", reply_markup=InlineKeyboardMarkup(buttons))
            return

        if data.startswith("user_banksel_"):
            _, _, tail = data.partition("user_banksel_")
            order_id, bank_id = tail.split("_BANK_", 1)
            bank_id = "BANK_" + bank_id
            resp = api_post(f"/order/{order_id}/select-bank", {"user_id": uid, "bank_id": bank_id})
            bank = resp["bank"]
            await query.message.reply_text(
                f"✅ بانک انتخاب شد\n\n"
                f"بانک: {bank['bank_name']}\n"
                f"صاحب حساب: {bank['owner_name']}\n"
                f"کارت: {bank['card_number']}\n"
                f"حساب: {bank['account_number']}\n"
                f"شبا: {bank['sheba']}\n\n"
                f"حالا از دکمه «ارسال رسید» استفاده کن."
            )
            return

        if data.startswith("user_receipt_"):
            order_id = data.replace("user_receipt_", "", 1)
            user_state[uid] = {"mode": "receipt", "order_id": order_id}
            await query.message.reply_text(f"📤 حالا عکس رسید سفارش {order_id} را بفرست")
            return

        if data.startswith("user_wallet_"):
            order_id = data.replace("user_wallet_", "", 1)
            resp = api_get(f"/order/{order_id}/wallet")
            wallet = resp["wallet"]
            await query.message.reply_text(
                f"👛 ولت سفارش {order_id}\n\n"
                f"ارز: {wallet['asset_code']}\n"
                f"شبکه: {wallet['network']}\n"
                f"آدرس: {wallet['address']}"
            )
            return

        if data.startswith("user_txid_"):
            order_id = data.replace("user_txid_", "", 1)
            user_state[uid] = {"mode": "txid", "order_id": order_id}
            await query.message.reply_text(f"🔗 حالا TXID سفارش {order_id} را بفرست")
            return

        if data.startswith("admin_approve_"):
            if uid != ADMIN_ID:
                return
            order_id = data.replace("admin_approve_", "", 1)
            resp = api_post(f"/admin/order/{order_id}/approve", {"admin_id": ADMIN_ID})
            await query.message.reply_text(f"✅ سفارش {order_id} تأیید شد → {resp['order']['status']}")
            return

        if data.startswith("admin_status_"):
            if uid != ADMIN_ID:
                return
            _, _, tail = data.partition("admin_status_")
            order_id, status = tail.rsplit("_", 1)
            resp = api_post(f"/admin/order/{order_id}/status", {"admin_id": ADMIN_ID, "status": status})
            await query.message.reply_text(f"✅ سفارش {order_id} → {resp['order']['status']}")
            return

    except Exception as e:
        await query.message.reply_text(f"❌ خطا: {e}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = user_state.get(uid)
    if not state or state.get("mode") != "receipt":
        await update.message.reply_text("اول از دکمه «ارسال رسید» استفاده کن.")
        return

    order_id = state["order_id"]
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    content = await file.download_as_bytearray()
    b64 = "data:image/jpeg;base64," + base64.b64encode(content).decode("utf-8")

    try:
        api_post(f"/order/{order_id}/upload-receipt", {"user_id": uid, "image_base64": b64})
        await update.message.reply_text("✅ رسید ثبت شد. منتظر بررسی ادمین باشید.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")
    finally:
        user_state.pop(uid, None)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()

    if text == "/start":
        return

    state = user_state.get(uid)
    if state and state.get("mode") == "txid":
        order_id = state["order_id"]
        try:
            api_post(f"/order/{order_id}/submit-txid", {"user_id": uid, "txid": text})
            await update.message.reply_text("✅ TXID ثبت شد. منتظر بررسی ادمین باشید.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {e}")
        finally:
            user_state.pop(uid, None)
        return

    await update.message.reply_text("از دکمه‌ها استفاده کن 👇", reply_markup=start_keyboard())


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is empty")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("myorders", my_orders))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()