import os
import json
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Shift definitions
SHIFTS = {
    1: {"name": {"ru": "Первая смена", "en": "First Shift"}, "start": "09:30", "end": "16:30"},
    2: {"name": {"ru": "Вторая смена", "en": "Second Shift"}, "start": "16:00", "end": "23:00"}
}

DATA_FILE = "shifts.json"

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"shifts": {}, "users": {}}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_language(user):
    """Determine user's language based on Telegram settings"""
    if user and user.language_code and user.language_code.startswith("ru"):
        return "ru"
    return "en"

def get_text(lang: str, key: str, **kwargs) -> str:
    """Return translated text based on user's language"""
    
    translations = {
        # Welcome and registration
        "welcome_new": {
            "ru": "✅ Добро пожаловать, {name}! Вы зарегистрированы.\n\n📅 **Команды:**\n/week - Просмотреть расписание\n/shift ГГГГ-ММ-ДД 1 - Первая смена (9:30-16:30)\n/shift ГГГГ-ММ-ДД 2 - Вторая смена (16:00-23:00)\n/my_shifts - Мои смены\n/cancel ГГГГ-ММ-ДД 1|2 - Отменить смену\n/help - Помощь",
            "en": "✅ Welcome, {name}! You're registered.\n\n📅 **Commands:**\n/week - View schedule\n/shift YYYY-MM-DD 1 - First Shift (9:30-16:30)\n/shift YYYY-MM-DD 2 - Second Shift (16:00-23:00)\n/my_shifts - Your shifts\n/cancel YYYY-MM-DD 1|2 - Cancel shift\n/help - Help"
        },
        "welcome_back": {
            "ru": "👋 С возвращением, {name}! Используйте /week для просмотра расписания.",
            "en": "👋 Welcome back, {name}! Use /week to view the schedule."
        },
        
        # Shift commands
        "shift_usage": {
            "ru": "📝 Использование: /shift ГГГГ-ММ-ДД 1|2\n\nПримеры:\n/shift 2026-04-20 1 - Первая смена (9:30-16:30)\n/shift 2026-04-20 2 - Вторая смена (16:00-23:00)",
            "en": "📝 Usage: /shift YYYY-MM-DD 1|2\n\nExamples:\n/shift 2026-04-20 1 - First Shift (9:30-16:30)\n/shift 2026-04-20 2 - Second Shift (16:00-23:00)"
        },
        "shift_added": {
            "ru": "✅ Вы добавлены в {shift} на {date} ({start} - {end})",
            "en": "✅ Added to {shift} on {date} ({start} - {end})"
        },
        "already_signed": {
            "ru": "❌ Вы уже записаны на {shift} на {date}!",
            "en": "❌ You're already signed up for {shift} on {date}!"
        },
        "past_date": {
            "ru": "❌ Нельзя записаться на прошедшую дату!",
            "en": "❌ Cannot sign up for past dates!"
        },
        "future_limit": {
            "ru": "❌ Пожалуйста, записывайтесь только на следующую неделю (максимум 7 дней вперёд)!",
            "en": "❌ Please sign up only for the upcoming week (maximum 7 days in advance)!"
        },
        "invalid_date": {
            "ru": "❌ Неверный формат даты! Используйте ГГГГ-ММ-ДД\nПример: /shift 2026-04-20 1",
            "en": "❌ Invalid date format! Use YYYY-MM-DD\nExample: /shift 2026-04-20 1"
        },
        "invalid_shift": {
            "ru": "❌ Смена должна быть 1 (Первая) или 2 (Вторая)",
            "en": "❌ Shift must be 1 (First) or 2 (Second)"
        },
        
        # View week schedule
        "week_schedule_header": {
            "ru": "📅 **Расписание смен (следующие 7 дней)**\n\n",
            "en": "📅 **Shift Schedule (Next 7 Days)**\n\n"
        },
        "first_shift_label": {
            "ru": "🌅 Первая смена (9:30-16:30): ",
            "en": "🌅 First Shift (9:30-16:30): "
        },
        "second_shift_label": {
            "ru": "🌙 Вторая смена (16:00-23:00): ",
            "en": "🌙 Second Shift (16:00-23:00): "
        },
        "no_one_signed": {
            "ru": "— Никто не записан —",
            "en": "— No one signed up —"
        },
        
        # My shifts
        "my_shifts_header": {
            "ru": "📋 **Ваши предстоящие смены:**\n\n",
            "en": "📋 **Your Upcoming Shifts:**\n\n"
        },
        "no_shifts": {
            "ru": "📋 У вас нет запланированных смен.",
            "en": "📋 You have no upcoming shifts scheduled."
        },
        
        # Cancel shift
        "cancel_usage": {
            "ru": "📝 Использование: /cancel ГГГГ-ММ-ДД 1|2\n\nПримеры:\n/cancel 2026-04-20 1 - Отменить первую смену\n/cancel 2026-04-20 2 - Отменить вторую смену",
            "en": "📝 Usage: /cancel YYYY-MM-DD 1|2\n\nExamples:\n/cancel 2026-04-20 1 - Cancel First Shift\n/cancel 2026-04-20 2 - Cancel Second Shift"
        },
        "no_shifts_for_date": {
            "ru": "❌ Нет смен на эту дату.",
            "en": "❌ No shifts found for that date."
        },
        "not_signed_for_shift": {
            "ru": "❌ Вы не записаны на эту смену.",
            "en": "❌ You're not signed up for that shift."
        },
        "shift_removed": {
            "ru": "✅ Вы удалены из {shift} на {date}",
            "en": "✅ Removed from {shift} on {date}"
        },
        
        # Help
        "help_text": {
            "ru": "📋 **Команды бота расписания смен**\n\n"
                   "/start - Зарегистрироваться\n"
                   "/week - Просмотреть расписание на следующую неделю\n"
                   "/shift ГГГГ-ММ-ДД 1 - Записаться на Первую смену (9:30-16:30)\n"
                   "/shift ГГГГ-ММ-ДД 2 - Записаться на Вторую смену (16:00-23:00)\n"
                   "/my_shifts - Посмотреть свои смены\n"
                   "/cancel ГГГГ-ММ-ДД 1|2 - Отменить запись на смену\n"
                   "/help - Показать эту справку\n\n"
                   "📌 **Формат даты:** ГГГГ-ММ-ДД (например, 2026-04-20)",
            "en": "📋 **Shift Bot Commands**\n\n"
                   "/start - Register\n"
                   "/week - View schedule for next 7 days\n"
                   "/shift YYYY-MM-DD 1 - Sign up for First Shift (9:30-16:30)\n"
                   "/shift YYYY-MM-DD 2 - Sign up for Second Shift (16:00-23:00)\n"
                   "/my_shifts - View your upcoming shifts\n"
                   "/cancel YYYY-MM-DD 1|2 - Cancel your shift\n"
                   "/help - Show this help message\n\n"
                   "📌 **Date format:** YYYY-MM-DD (e.g., 2026-04-20)"
        }
    }
    
    # Default to English if translation missing
    if key not in translations:
        return f"Missing translation for: {key}"
    
    if lang not in translations[key]:
        lang = "en"
    
    text = translations[key][lang]
    
    # Format with kwargs if provided
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    
    return text

# ----- Telegram Command Handlers -----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register a new user"""
    user = update.effective_user
    lang = get_language(user)
    username = f"@{user.username}" if user.username else user.full_name
    
    data = load_data()
    if username not in data["users"]:
        data["users"][username] = {
            "telegram_id": user.id,
            "name": user.full_name,
            "language": lang
        }
        save_data(data)
        text = get_text(lang, "welcome_new", name=user.full_name)
    else:
        text = get_text(lang, "welcome_back", name=user.full_name)
    
    await update.message.reply_text(text)

async def add_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add employee to a shift"""
    user = update.effective_user
    lang = get_language(user)
    
    if len(context.args) != 2:
        await update.message.reply_text(get_text(lang, "shift_usage"))
        return
    
    date_str, shift_num = context.args[0], context.args[1]
    username = f"@{user.username}" if user.username else user.full_name
    
    # Validate date
    try:
        shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if shift_date < datetime.now().date():
            await update.message.reply_text(get_text(lang, "past_date"))
            return
        if shift_date > datetime.now().date() + timedelta(days=7):
            await update.message.reply_text(get_text(lang, "future_limit"))
            return
    except ValueError:
        await update.message.reply_text(get_text(lang, "invalid_date"))
        return
    
    # Validate shift number
    if shift_num not in ["1", "2"]:
        await update.message.reply_text(get_text(lang, "invalid_shift"))
        return
    
    data = load_data()
    date_key = date_str
    
    if date_key not in data["shifts"]:
        data["shifts"][date_key] = {"first": [], "second": []}
    
    shift_key = "first" if shift_num == "1" else "second"
    
    if username in data["shifts"][date_key][shift_key]:
        shift_name = SHIFTS[int(shift_num)]["name"][lang]
        await update.message.reply_text(get_text(lang, "already_signed", shift=shift_name, date=date_str))
        return
    
    data["shifts"][date_key][shift_key].append(username)
    save_data(data)
    
    shift_name = SHIFTS[int(shift_num)]["name"][lang]
    shift_start = SHIFTS[int(shift_num)]["start"]
    shift_end = SHIFTS[int(shift_num)]["end"]
    
    await update.message.reply_text(get_text(lang, "shift_added", shift=shift_name, date=date_str, start=shift_start, end=shift_end))

async def view_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the schedule for the next 7 days"""
    user = update.effective_user
    lang = get_language(user)
    data = load_data()
    today = datetime.now().date()
    
    message = get_text(lang, "week_schedule_header")
    
    # Weekday names in Russian and English
    weekdays = {
        "ru": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
        "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    }
    
    for i in range(7):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        # Get weekday index (Monday=0)
        weekday_idx = date.weekday()
        weekday_name = weekdays[lang][weekday_idx]
        
        message += f"**{weekday_name} ({date_str})**\n"
        
        # First shift
        first_shift = data["shifts"].get(date_str, {}).get("first", [])
        first_display = ", ".join(first_shift) if first_shift else get_text(lang, "no_one_signed")
        message += f"{get_text(lang, 'first_shift_label')}{first_display}\n"
        
        # Second shift
        second_shift = data["shifts"].get(date_str, {}).get("second", [])
        second_display = ", ".join(second_shift) if second_shift else get_text(lang, "no_one_signed")
        message += f"{get_text(lang, 'second_shift_label')}{second_display}\n\n"
    
    await update.message.reply_text(message)

async def my_shifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's upcoming shifts"""
    user = update.effective_user
    lang = get_language(user)
    username = f"@{user.username}" if user.username else user.full_name
    data = load_data()
    today = datetime.now().date()
    
    my_upcoming = []
    for date_str, shifts in data["shifts"].items():
        try:
            shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if shift_date >= today:
                if username in shifts.get("first", []):
                    my_upcoming.append(f"{date_str}: {SHIFTS[1]['name'][lang]} (9:30-16:30)")
                if username in shifts.get("second", []):
                    my_upcoming.append(f"{date_str}: {SHIFTS[2]['name'][lang]} (16:00-23:00)")
        except:
            pass
    
    if my_upcoming:
        message = get_text(lang, "my_shifts_header") + "\n".join(my_upcoming)
    else:
        message = get_text(lang, "no_shifts")
    
    await update.message.reply_text(message)

async def cancel_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel user's shift"""
    user = update.effective_user
    lang = get_language(user)
    
    if len(context.args) != 2:
        await update.message.reply_text(get_text(lang, "cancel_usage"))
        return
    
    date_str, shift_num = context.args[0], context.args[1]
    username = f"@{user.username}" if user.username else user.full_name
    
    data = load_data()
    shift_key = "first" if shift_num == "1" else "second"
    
    if date_str not in data["shifts"]:
        await update.message.reply_text(get_text(lang, "no_shifts_for_date"))
        return
    
    if username not in data["shifts"][date_str][shift_key]:
        await update.message.reply_text(get_text(lang, "not_signed_for_shift"))
        return
    
    data["shifts"][date_str][shift_key].remove(username)
    save_data(data)
    
    shift_name = SHIFTS[int(shift_num)]["name"][lang]
    await update.message.reply_text(get_text(lang, "shift_removed", shift=shift_name, date=date_str))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    user = update.effective_user
    lang = get_language(user)
    await update.message.reply_text(get_text(lang, "help_text"))

# ----- Main Function -----

def main():
    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN environment variable not set!")
        return
    
    logger.info("🤖 Starting shift schedule bot...")
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("shift", add_shift))
    app.add_handler(CommandHandler("week", view_week))
    app.add_handler(CommandHandler("my_shifts", my_shifts))
    app.add_handler(CommandHandler("cancel", cancel_shift))
    app.add_handler(CommandHandler("help", help_command))
    
    logger.info("✅ Bot is running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()