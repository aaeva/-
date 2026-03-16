import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8720594664:AAHWu41HWPk3K6NTU-jatYuEV3sVaekghhw"
FILE = "shop_accounting_template.xlsx"


def load_sheet(name):
    return pd.read_excel(FILE, sheet_name=name)


def save_sheet(df, name):
    with pd.ExcelWriter(FILE, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        df.to_excel(writer, sheet_name=name, index=False)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
    Бот учета магазина

    /add_product название закупка продажа
    /restock название количество
    /sell название количество
    /inventory
    /report_day
    /report_week
    """
    await update.message.reply_text(text)


async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):

    name = context.args[0]
    buy = float(context.args[1])
    sell = float(context.args[2])
    products = load_sheet("products")

    new_id = len(products) + 1
    showcase = load_sheet("showcase")
    showcase.loc[len(showcase)] = [new_id, name, 0, 0, 0]
    save_sheet(showcase, "showcase")
    products.loc[len(products)] = [new_id, name, buy, sell]

    save_sheet(products, "products")

    inventory = load_sheet("inventory")
    inventory.loc[len(inventory)] = [new_id, name, 0, 0]

    save_sheet(inventory, "inventory")

    await update.message.reply_text("Товар добавлен")

async def to_showcase(update: Update, context: ContextTypes.DEFAULT_TYPE):

    name = context.args[0]
    qty = int(context.args[1])

    inventory = load_sheet("inventory")
    showcase = load_sheet("showcase")

    inv_rows = inventory[inventory["name"] == name]

    if inv_rows.empty:
        await update.message.reply_text("Товар не найден на складе")
        return

    inv_index = inv_rows.index[0]

    if inventory.at[inv_index, "warehouse_left"] < qty:
        await update.message.reply_text("На складе недостаточно товара")
        return

    # уменьшаем склад
    inventory.at[inv_index, "moved_to_showcase"] += qty
    inventory.at[inv_index, "warehouse_left"] -= qty

    save_sheet(inventory, "inventory")

    show_rows = showcase[showcase["name"] == name]

    if show_rows.empty:
        await update.message.reply_text("Товар не найден в витрине")
        return

    show_index = show_rows.index[0]

    showcase.at[show_index, "showcase_total"] += qty
    showcase.at[show_index, "showcase_left"] += qty

    save_sheet(showcase, "showcase")

    await update.message.reply_text(f"На витрину вынесено {qty} {name}")

async def restock(update: Update, context: ContextTypes.DEFAULT_TYPE):

    name = context.args[0]
    qty = int(context.args[1])

    restock = load_sheet("restock")
    inventory = load_sheet("inventory")
    products = load_sheet("products")

    product = products[products["name"] == name]

    if product.empty:
        await update.message.reply_text("Товар не найден")
        return

    product_id = product.iloc[0]["product_id"]
    buy_price = product.iloc[0]["buy_price"]

    restock.loc[len(restock)] = [
        pd.Timestamp.today(),
        product_id,
        name,
        qty,
        buy_price,
        qty * buy_price
    ]

    save_sheet(restock, "restock")

    index = inventory[inventory["name"] == name].index[0]

    inventory.at[index, "stock_quantity"] += qty
    inventory.at[index, "stock_value"] += qty * buy_price

    save_sheet(inventory, "inventory")

    await update.message.reply_text("Пополнение записано")


async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):

    name = context.args[0]
    qty = int(context.args[1])

    sales = load_sheet("sales")
    showcase = load_sheet("showcase")
    products = load_sheet("products")

    product = products[products["name"] == name]

    if product.empty:
        await update.message.reply_text("Товар не найден")
        return

    sell_price = product.iloc[0]["sell_price"]
    buy_price = product.iloc[0]["buy_price"]
    product_id = product.iloc[0]["product_id"]

    index = showcase[showcase["name"] == name].index

    if len(index) == 0:
        await update.message.reply_text("Товар не найден на витрине")
        return

    index = index[0]

    if showcase.at[index, "showcase_left"] < qty:
        await update.message.reply_text("Недостаточно товара на витрине")
        return

    # уменьшаем витрину
    showcase.at[index, "sold"] += qty
    showcase.at[index, "showcase_left"] -= qty

    save_sheet(showcase, "showcase")

    revenue = qty * sell_price
    profit = qty * (sell_price - buy_price)

    # записываем продажу
    sales.loc[len(sales)] = [
        pd.Timestamp.today(),
        product_id,
        name,
        qty,
        sell_price,
        revenue,
        profit
    ]

    save_sheet(sales, "sales")

    await update.message.reply_text(
        f"""
Продажа выполнена

Товар: {name}
Количество: {qty}

Выручка: {revenue}
Прибыль: {profit}
"""
    )

async def showcase_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):

    showcase = load_sheet("showcase")

    text = "Витрина:\n\n"

    for _, row in showcase.iterrows():
        text += f"{row['name']} — {row['showcase_left']}\n"

    await update.message.reply_text(text)


async def inventory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):

    inventory = load_sheet("inventory")

    text = "Склад:\n\n"

    for _, row in inventory.iterrows():
        text += f"{row['name']} — {row['stock_quantity']}\n"

    await update.message.reply_text(text)


async def report_day(update: Update, context: ContextTypes.DEFAULT_TYPE):

    sales = load_sheet("sales")

    today = pd.Timestamp.today().date()

    sales_today = sales[pd.to_datetime(sales["date"]).dt.date == today]

    total = sales_today["revenue"].sum()
    profit = sales_today["profit"].sum()

    await update.message.reply_text(
        f"Отчет за сегодня\n\nВыручка: {total}\nПрибыль: {profit}"
    )
async def report_week(update: Update, context: ContextTypes.DEFAULT_TYPE):

    sales = load_sheet("sales")

    today = pd.Timestamp.today()
    week_ago = today - pd.Timedelta(days=7)

    sales["date"] = pd.to_datetime(sales["date"])

    sales_week = sales[(sales["date"] >= week_ago) & (sales["date"] <= today)]

    total = sales_week["revenue"].sum()
    profit = sales_week["profit"].sum()

    await update.message.reply_text(
        f"Отчет за неделю\n\nВыручка: {total}\nПрибыль: {profit}"
    )

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("add", add_product))
app.add_handler(CommandHandler("restock", restock))
app.add_handler(CommandHandler("sell", sell))
app.add_handler(CommandHandler("inventory", inventory_cmd))
app.add_handler(CommandHandler("report_day", report_day))
app.add_handler(CommandHandler("report_week", report_week))
app.add_handler(CommandHandler("to_showcase", to_showcase))
app.add_handler(CommandHandler("showcase", showcase_cmd))
print("Bot started")

app.run_polling()