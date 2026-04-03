import os
import json
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    logger.error("NO TOKEN FOUND!")
    exit(1)

DATA_FILE = "shifts.json"

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"shifts": {}}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name
    
    welcome_message = f"""
👋 Здравствуйте, {user_name}!

Добро пожаловать в бот управления сменами.

📅 **Доступные команды:**
/week - Посмотреть расписание на неделю
/shift ГГГГ-ММ-ДД 1 - Первая смена (9:30-16:30)
/shift ГГГГ-ММ-ДД 2 - Вторая смена (16:00-23:00)
/my_shifts - Мои смены
/cancel ГГГГ-ММ-ДД 1|2 - Отменить запись

📌 **Пример:**
/shift 2026-04-20 1

Хорошего дня! ☀️
"""
    await update.message.reply_text(welcome_message)

async def add_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("📝 Использование: /shift ГГГГ-ММ-ДД 1|2")
        return
    
    date_str = context.args[0]
    shift_num = context.args[1]
    user = update.effective_user
    user_name = user.username if user.username else user.full_name
    
    # Validate date
    try:
        shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if shift_date < datetime.now().date():
            await update.message.reply_text("❌ Нельзя записаться на прошедшую дату!")
            return
        if shift_date > datetime.now().date() + timedelta(days=7):
            await update.message.reply_text("❌ Записывайтесь только на следующую неделю!")
            return
    except ValueError:
        await update.message.reply_text("❌ Неверный формат даты! Используйте ГГГГ-ММ-ДД")
        return
    
    if shift_num not in ["1", "2"]:
        await update.message.reply_text("❌ Смена должна быть 1 или 2")
        return
    
    data = load_data()
    if date_str not in data["shifts"]:
        data["shifts"][date_str] = {"first": [], "second": []}
    
    key = "first" if shift_num == "1" else "second"
    full_user_name = f"@{user_name}" if user_name else user.full_name
    
    if full_user_name not in data["shifts"][date_str][key]:
        data["shifts"][date_str][key].append(full_user_name)
        save_data(data)
        shift_name = "первую смену (9:30-16:30)" if shift_num == "1" else "вторую смену (16:00-23:00)"
        await update.message.reply_text(f"✅ Вы записаны на {shift_name} на {date_str}")
    else:
        await update.message.reply_text("❌ Вы уже записаны на эту смену!")

async def view_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    today = datetime.now().date()
    
    weekdays_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    
    msg = "📅 **Расписание смен на следующую неделю:**\n\n"
    
    for i in range(7):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        weekday = weekdays_ru[date.weekday()]
        
        shifts = data["shifts"].get(date_str, {"first": [], "second": []})
        
        first = ', '.join(shifts['first']) if shifts['first'] else "— Никто не записан —"
        second = ', '.join(shifts['second']) if shifts['second'] else "— Никто не записан —"
        
        msg += f"*{weekday} ({date_str})*\n"
        msg += f"🌅 Первая смена (9:30-16:30): {first}\n"
        msg += f"🌙 Вторая смена (16:00-23:00): {second}\n\n"
    
    await update.message.reply_text(msg)

async def my_shifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = f"@{user.username}" if user.username else user.full_name
    data = load_data()
    today = datetime.now().date()
    my_list = []
    
    for date_str, shifts in data["shifts"].items():
        try:
            shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if shift_date >= today:
                if user_name in shifts.get("first", []):
                    my_list.append(f"📅 {date_str}: Первая смена (9:30-16:30)")
                if user_name in shifts.get("second", []):
                    my_list.append(f"📅 {date_str}: Вторая смена (16:00-23:00)")
        except:
            pass
    
    if my_list:
        msg = "📋 **Ваши предстоящие смены:**\n\n" + "\n".join(my_list)
    else:
        msg = "📋 У вас нет запланированных смен."
    
    await update.message.reply_text(msg)

async def cancel_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("📝 Использование: /cancel ГГГГ-ММ-ДД 1|2")
        return
    
    date_str = context.args[0]
    shift_num = context.args[1]
    user = update.effective_user
    user_name = f"@{user.username}" if user.username else user.full_name
    
    data = load_data()
    key = "first" if shift_num == "1" else "second"
    
    if date_str in data["shifts"] and user_name in data["shifts"][date_str][key]:
        data["shifts"][date_str][key].remove(user_name)
        save_data(data)
        shift_name = "первой смены" if shift_num == "1" else "второй смены"
        await update.message.reply_text(f"✅ Вы отменены от {shift_name} на {date_str}")
    else:
        await update.message.reply_text("❌ Вы не записаны на эту смену")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📋 **Команды бота:**

/start - Показать приветствие
/week - Расписание на неделю
/shift ГГГГ-ММ-ДД 1|2 - Записаться на смену
/my_shifts - Мои смены
/cancel ГГГГ-ММ-ДД 1|2 - Отменить запись
/help - Эта справка

📌 **Формат даты:** 2026-04-20
"""
    await update.message.reply_text(help_text)

def main():
    """Start the bot"""
    logger.info("🤖 Starting shift schedule bot...")
    
    # Create application
    app = Application.builder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("shift", add_shift))
    app.add_handler(CommandHandler("week", view_week))
    app.add_handler(CommandHandler("my_shifts", my_shifts))
    app.add_handler(CommandHandler("cancel", cancel_shift))
    app.add_handler(CommandHandler("help", help_command))
    
    logger.info("✅ Bot is running!")
    
    # Start polling
    app.run_polling()

if __name__ == "__main__":
    main()