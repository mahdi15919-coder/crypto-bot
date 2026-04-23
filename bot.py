import json
from typing import Any, Dict, List

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
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

# توکن را خودت اینجا بگذار
TOKEN = "6651322898:AAHMYTqY7S38AmaygN7EgZwWz2yQCvdz3ig"

# آیدی ادمین
ADMIN_ID = 5869677184

# آدرس Mini App
WEBAPP_URL = "https://crypto-bot-three-ruby.vercel.app/index.html"

CONFIG_FILE = "config.json"
ORDERS_FILE = "orders.json"


def load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def load_config() -> Dict[str, Any]:
    return load_json(CONFIG_FILE, {})


def load_orders() -> List[Dict[str, Any]]:
    return load_json(ORDERS_FILE, [])


def format_irr(value: float) -> str:
    return f"{int(round(value)):,}"


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


def get_user_orders(user_id: int) -> List[Dict[str, Any]]:
    orders = load_orders()
    return [o for o in orders if o.get("user_id") == user_id]


def render_order_text(order: Dict[str, Any]) -> str:
    side_text = "خرید" if order["side"] == "buy" else "فروش"
    return (
        "📦 اطلاعات سفارش\n\n"
        f"کد سفارش: {order['order_id']}\n"
        f"نوع: {side_text}\n"
        f"ارز: {order['asset_code']}\n"
        f"شبکه: {order['network']}\n"
        f"مقدار: {order['amount']}\n"
        f"مبلغ نهایی: {format_irr(order['total_irr'])} ریال\n"
        f"وضعیت: {order['status']}"
    )


def start_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 ورود به پنل", web_app=WebAppInfo(url=WEBAPP_URL))],
        [
            InlineKeyboardButton("💵 قیمت تتر", callback_data="menu_price"),
            InlineKeyboardButton("📦 سفارش‌های من", callback_data="menu_myorders"),
        ],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="menu_help")],
    ])


def start_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🚀 ورود به پنل", web_app=WebAppInfo(url=WEBAPP_URL))],
            ["💵 قیمت تتر", "📦 سفارش‌های من"],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.set_chat_menu_button(
        chat_id=update.effective_chat.id,
        menu_button=MenuButtonWebApp(
            text="پنل",
            web_app=WebAppInfo(url=WEBAPP_URL),
        ),
    )

    text = (
        "🚀 خوش اومدی\n\n"
        "برای تجربه بهتر از دکمه ورود به پنل استفاده کن.\n"
        "همه مراحل اصلی خرید و فروش داخل Mini App انجام می‌شود."
    )

    await update.message.reply_text(text, reply_markup=start_inline_keyboard())
    await update.message.reply_text("👇 دسترسی سریع", reply_markup=start_reply_keyboard())


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    usdt_prices = get_usdt_buy_sell_prices(config)

    text = (
        "💵 قیمت تتر\n\n"
        f"🟢 فروش به شما: {format_irr(usdt_prices['sell_to_user'])} ریال\n"
        f"🔴 خرید از شما: {format_irr(usdt_prices['buy_from_user'])} ریال"
    )
    await update.message.reply_text(text)


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    orders = get_user_orders(user_id)

    if not orders:
        await update.message.reply_text("📭 هنوز سفارشی نداری")
        return

    for order in orders[-10:]:
        await update.message.reply_text(render_order_text(order))


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ دسترسی نداری")
        return

    await update.message.reply_text(
        f"🛠 پنل ادمین\n\nبرای پنل کامل از Mini App استفاده کن:\n{WEBAPP_URL}"
    )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    config = load_config()

    if data == "menu_price":
        usdt_prices = get_usdt_buy_sell_prices(config)
        await query.message.reply_text(
            "💵 قیمت تتر\n\n"
            f"🟢 فروش به شما: {format_irr(usdt_prices['sell_to_user'])} ریال\n"
            f"🔴 خرید از شما: {format_irr(usdt_prices['buy_from_user'])} ریال"
        )
        return

    if data == "menu_myorders":
        user_id = query.from_user.id
        orders = get_user_orders(user_id)

        if not orders:
            await query.message.reply_text("📭 هنوز سفارشی نداری")
            return

        for order in orders[-10:]:
            await query.message.reply_text(render_order_text(order))
        return

    if data == "menu_help":
        await query.message.reply_text(
            "ℹ️ راهنما\n\n"
            "• قیمت تتر را از دکمه قیمت ببین\n"
            "• برای خرید و فروش وارد پنل شو\n"
            "• سفارش‌های ثبت‌شده را از بخش سفارش‌های من ببین"
        )
        return


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if text == "💵 قیمت تتر":
        await price(update, context)
        return

    if text == "📦 سفارش‌های من":
        await my_orders(update, context)
        return

    await update.message.reply_text("از دکمه‌ها استفاده کن 👇", reply_markup=start_inline_keyboard())


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("myorders", my_orders))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()