from database import init_database, add_user, get_user
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = "8954124854:AAGczlEeHPxiT1saoytPzrXHhLHPhXWia6A"

WEBAPP_URL = "https://sayboi.netlify.app"

menu = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📚 My Course", web_app=WebAppInfo(WEBAPP_URL))],
        [KeyboardButton("👤 Profile"), KeyboardButton("📈 Progress")],
        [KeyboardButton("💬 Support")]
    ],
    resize_keyboard=True
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    add_user(
        telegram_id=user.id,
        username=user.username or ""
    )

    await update.message.reply_text(
        f"""👋 Welcome, {user.first_name}!

Welcome to SAY BOI.

Choose an option below.""",
        reply_markup=menu
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text

    if text == "👤 Profile":

        await update.message.reply_text(
            "👤 Profile\n\n"
            "Premium: ❌\n"
            "Progress: 0%\n"
            "Lessons completed: 0"
        )

    elif text == "📈 Progress":

        await update.message.reply_text(
            "📈 Progress\n\n□□□□□□□□□□\n0%"
        )

    elif text == "💬 Support":

        await update.message.reply_text(
            "Support:\n\n@sayboi_support"
        )


def main():

    init_database()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            buttons
        )
    )

    print("Bot started.")

    app.run_polling()


if __name__ == "__main__":
    main()
