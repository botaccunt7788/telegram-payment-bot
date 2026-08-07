import os
import sqlite3

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)


TOKEN = os.environ["TOKEN"]


# Database
db = sqlite3.connect("payments.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS payments(
    name TEXT,
    amount INTEGER
)
""")

db.commit()


# Check if user is admin
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id
    )

    return member.status in [
        "administrator",
        "creator"
    ]


# Add payment (+50, +100 etc.)
async def add_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        await update.message.reply_text(
            "❌ Only group admins can add payments."
        )
        return

    text = update.message.text

    try:
        amount = int(text[1:])
    except ValueError:
        return

    name = update.message.from_user.first_name

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?)",
        (name, amount)
    )

    db.commit()


    # Total amount
    cursor.execute(
        "SELECT SUM(amount) FROM payments"
    )

    total_amount = cursor.fetchone()[0] or 0


    # Latest payments
    cursor.execute("""
        SELECT name, amount
        FROM payments
        ORDER BY rowid DESC
        LIMIT 2
    """)

    latest = cursor.fetchall()


    message = "💰 Payment Update\n\n"
    message += "🆕 Latest payments:\n"

    for payment_name, payment_amount in latest:
        message += f"• {payment_name}: {payment_amount}\n"


    message += f"\n📊 Total: {total_amount}"


    await update.message.reply_text(message)



# Show payment report
async def total(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        await update.message.reply_text(
            "❌ Only group admins can use this command."
        )
        return


    cursor.execute("""
        SELECT name, SUM(amount)
        FROM payments
        GROUP BY name
    """)

    rows = cursor.fetchall()


    message = "💰 Payment Report\n\n"
    total_amount = 0


    for name, amount in rows:
        message += f"{name}: {amount}\n"
        total_amount += amount


    message += f"\n📊 Total: {total_amount}"


    await update.message.reply_text(message)



# Reset payments
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        await update.message.reply_text(
            "❌ Only group admins can reset payments."
        )
        return


    cursor.execute("DELETE FROM payments")
    db.commit()


    await update.message.reply_text(
        "♻️ All payments have been reset."
    )



# Start bot
def main():

    app = Application.builder().token(TOKEN).build()


    # Messages like +50, +100
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^\+\d+$"),
            add_payment
        )
    )


    app.add_handler(
        CommandHandler("total", total)
    )


    app.add_handler(
        CommandHandler("reset", reset)
    )


    print("KK Payments Bot is running...")


    app.run_polling()



if __name__ == "__main__":
    main()