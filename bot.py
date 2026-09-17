import os

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
    filters,
    TypeHandler
)

CHANNEL_ID = -1004410613751

TOKEN = os.getenv("TELEGRAM_TOKEN")

PLATFORM_URL = os.getenv("PLATFORM_URL", "https://sayboi-backend.onrender.com")


menu = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🔑 Особистий кабінет", web_app=WebAppInfo(f"{PLATFORM_URL}/login"))],
        [
            KeyboardButton("👤 Профіль", web_app=WebAppInfo(f"{PLATFORM_URL}/student/profile")),
            KeyboardButton("📈 Прогрес", web_app=WebAppInfo(f"{PLATFORM_URL}/student"))
        ],
        [KeyboardButton("💬 Підтримка")]
    ],
    resize_keyboard=True
)

async def create_channel_invite(bot, telegram_id):

    invite = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        name=f"premium_{telegram_id}",
        member_limit=1
    )

    return invite.invite_link
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    add_user(
        telegram_id=user.id,
        username=user.username or ""
    )

    await update.message.reply_text(
        f"""👋 Вітаємо, {user.first_name}!

Ласкаво просимо до SAY BOI.

Обери опцію нижче.""",
        reply_markup=menu
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text

    if text == "💬 Підтримка":

        await update.message.reply_text(
            "Підтримка:\n\n"
            "@sayboi_support"
        )


async def channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.channel_post:

        print("================================")
        print("CHANNEL ID:", update.channel_post.chat.id)
        print("CHANNEL:", update.channel_post.chat.title)
        print("================================")


def main():

    init_database()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        TypeHandler(Update, channel_post)
    )

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
