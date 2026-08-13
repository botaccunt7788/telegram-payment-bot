import os
import sqlite3
import threading

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)


TOKEN = os.environ["TOKEN"]


# ============================================================
# DATABASE
# ============================================================

db = sqlite3.connect(
    "payments.db",
    check_same_thread=False
)

cursor = db.cursor()
db_lock = threading.Lock()


# Create payments table if it does not exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS payments(
    name TEXT,
    amount INTEGER
)
""")

db.commit()


# Add chat_id to the existing database if it is not already there.
# This allows each Telegram group to have separate records.
try:
    cursor.execute(
        "ALTER TABLE payments ADD COLUMN chat_id INTEGER"
    )
    db.commit()
except sqlite3.OperationalError:
    # Column already exists
    pass


# ============================================================
# CHECK IF USER IS ADMIN
# ============================================================

async def is_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id
    )

    return member.status in [
        "administrator",
        "creator"
    ]


# ============================================================
# ADD / SUBTRACT PAYMENT
# ============================================================

async def add_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # Only admins can add or subtract payments
    if not await is_admin(update, context):
        await update.message.reply_text(
            "❌ Only group admins can add or subtract payments."
        )
        return


    # The + or - message MUST be a reply to the employee's
    # payment screenshot.
    replied_message = update.message.reply_to_message

    if not replied_message:
        await update.message.reply_text(
            "⚠️ Please reply directly to the employee's "
            "payment screenshot with +amount or -amount."
        )
        return


    # Make sure the admin is replying to a photo/screenshot
    if not replied_message.photo:
        await update.message.reply_text(
            "⚠️ Please reply directly to the payment "
            "screenshot with +amount or -amount."
        )
        return


    text = update.message.text.strip()


    # Accept:
    # +20
    # +100
    # -1
    # -100
    try:
        amount = int(text)

    except ValueError:
        return


    # Do not allow 0
    if amount == 0:
        await update.message.reply_text(
            "⚠️ Amount cannot be 0."
        )
        return


    # Get the person who sent the screenshot
    depositor = replied_message.from_user

    if not depositor:
        await update.message.reply_text(
            "⚠️ Could not identify the person who sent "
            "the payment screenshot."
        )
        return


    depositor_name = depositor.first_name
    chat_id = update.effective_chat.id


    # ========================================================
    # SAVE PAYMENT
    # ========================================================

    with db_lock:

        cursor.execute(
            """
            INSERT INTO payments (
                name,
                amount,
                chat_id
            )
            VALUES (?, ?, ?)
            """,
            (
                depositor_name,
                amount,
                chat_id
            )
        )

        db.commit()


        # ====================================================
        # TOTAL FOR THIS GROUP ONLY
        # ====================================================

        cursor.execute(
            """
            SELECT SUM(amount)
            FROM payments
            WHERE chat_id = ?
            """,
            (chat_id,)
        )

        total_amount = cursor.fetchone()[0] or 0


        # ====================================================
        # LATEST 2 PAYMENTS FOR THIS GROUP
        # ====================================================

        cursor.execute(
            """
            SELECT name, amount
            FROM payments
            WHERE chat_id = ?
            ORDER BY rowid DESC
            LIMIT 2
            """,
            (chat_id,)
        )

        latest = cursor.fetchall()


    # We received newest first.
    # Reverse it so the older recent payment appears first.
    latest = list(reversed(latest))


    # ========================================================
    # PAYMENT UPDATE MESSAGE
    # ========================================================

    message = "💰 Payment Update\n\n"
    message += "🆕 Latest payments:\n"


    for payment_name, payment_amount in latest:

        # Display + for positive payments
        if payment_amount > 0:
            display_amount = f"+{payment_amount}"
        else:
            display_amount = str(payment_amount)

        message += (
            f"• {payment_name}: {display_amount}\n"
        )


    message += f"\n📊 Total: {total_amount}"


    await update.message.reply_text(message)


# ============================================================
# SHOW PAYMENT REPORT
# ============================================================

async def total(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await is_admin(update, context):
        await update.message.reply_text(
            "❌ Only group admins can use this command."
        )
        return


    chat_id = update.effective_chat.id


    with db_lock:

        cursor.execute(
            """
            SELECT name, SUM(amount)
            FROM payments
            WHERE chat_id = ?
            GROUP BY name
            """,
            (chat_id,)
        )

        rows = cursor.fetchall()


    message = "💰 Payment Report\n\n"
    total_amount = 0


    for name, amount in rows:

        message += f"{name}: {amount}\n"

        total_amount += amount


    message += f"\n📊 Total: {total_amount}"


    await update.message.reply_text(message)


# ============================================================
# RESET PAYMENTS
# ============================================================

async def reset(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await is_admin(update, context):
        await update.message.reply_text(
            "❌ Only group admins can reset payments."
        )
        return


    chat_id = update.effective_chat.id


    with db_lock:

        cursor.execute(
            """
            DELETE FROM payments
            WHERE chat_id = ?
            """,
            (chat_id,)
        )

        db.commit()


    await update.message.reply_text(
        "♻️ All payments have been reset."
    )


# ============================================================
# START BOT
# ============================================================

def main():

    app = Application.builder().token(TOKEN).build()


    # --------------------------------------------------------
    # +20, +100, -1, -100, etc.
    # --------------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^[+-]\d+$"),
            add_payment
        )
    )


    # --------------------------------------------------------
    # COMMANDS
    # --------------------------------------------------------

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
