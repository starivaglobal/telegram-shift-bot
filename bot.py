import os
import json
import logging
from datetime import datetime, timedelta
from telegram.ext import Updater, CommandHandler
from telegram import ParseMode

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

def start(update, context):
    update.message.reply_text("Welcome to Shift Bot!\n\nUse /week to see schedule\nUse /shift YYYY-MM-DD 1 or 2")

def add_shift(update, context):
    args = context.args
    if len(args) != 2:
        update.message.reply_text("Usage: /shift YYYY-MM-DD 1|2")
        return
    
    date_str = args[0]
    shift_num = args[1]
    user = update.effective_user
    user_name = user.username if user.username else user.full_name
    
    data = load_data()
    if date_str not in data["shifts"]:
        data["shifts"][date_str] = {"first": [], "second": []}
    
    key = "first" if shift_num == "1" else "second"
    
    if f"@{user_name}" not in data["shifts"][date_str][key]:
        data["shifts"][date_str][key].append(f"@{user_name}")
        save_data(data)
        update.message.reply_text(f"✅ Added to shift {shift_num} on {date_str}")
    else:
        update.message.reply_text("❌ Already signed up!")

def view_week(update, context):
    data = load_data()
    today = datetime.now().date()
    msg = "📅 **Schedule:**\n\n"
    
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    for i in range(7):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        weekday = weekdays[date.weekday()]
        
        shifts = data["shifts"].get(date_str, {"first": [], "second": []})
        
        first = ', '.join(shifts['first']) if shifts['first'] else "— empty —"
        second = ', '.join(shifts['second']) if shifts['second'] else "— empty —"
        
        msg += f"*{weekday} ({date_str})*\n"
        msg += f"🌅 First Shift (9:30-16:30): {first}\n"
        msg += f"🌙 Second Shift (16:00-23:00): {second}\n\n"
    
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

def my_shifts(update, context):
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
                    my_list.append(f"📅 {date_str}: First Shift (9:30-16:30)")
                if user_name in shifts.get("second", []):
                    my_list.append(f"📅 {date_str}: Second Shift (16:00-23:00)")
        except:
            pass
    
    if my_list:
        msg = "📋 **Your upcoming shifts:**\n\n" + "\n".join(my_list)
    else:
        msg = "📋 You have no upcoming shifts."
    
    update.message.reply_text(msg)

def cancel_shift(update, context):
    args = context.args
    if len(args) != 2:
        update.message.reply_text("Usage: /cancel YYYY-MM-DD 1|2")
        return
    
    date_str = args[0]
    shift_num = args[1]
    user = update.effective_user
    user_name = f"@{user.username}" if user.username else user.full_name
    
    data = load_data()
    key = "first" if shift_num == "1" else "second"
    
    if date_str in data["shifts"] and user_name in data["shifts"][date_str][key]:
        data["shifts"][date_str][key].remove(user_name)
        save_data(data)
        update.message.reply_text(f"✅ Cancelled shift {shift_num} on {date_str}")
    else:
        update.message.reply_text("❌ You are not signed up for that shift")

def main():
    logger.info("🤖 Starting shift bot...")
    
    # Create the Updater (old API)
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Add handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("shift", add_shift))
    dp.add_handler(CommandHandler("week", view_week))
    dp.add_handler(CommandHandler("my_shifts", my_shifts))
    dp.add_handler(CommandHandler("cancel", cancel_shift))
    
    # Start the bot
    updater.start_polling()
    logger.info("✅ Bot is running!")
    
    # Keep running
    updater.idle()

if __name__ == "__main__":
    main()