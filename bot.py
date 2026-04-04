import os
import json
import logging
from datetime import datetime, timedelta
import requests
import threading
import time
from flask import Flask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("NO TOKEN FOUND!")
    exit(1)

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
DATA_FILE = "shifts.json"

# Flask app for health check
flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/healthcheck')
def health_check():
    return "OK", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"shifts": {}}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def get_display_name(user):
    """Extract display name from user object with priority: Full Name > Username > User ID"""
    first_name = user.get("first_name", "")
    last_name = user.get("last_name", "")
    username = user.get("username", "")
    user_id = user.get("id", "")
    
    if first_name:
        if last_name:
            return f"{first_name} {last_name}"
        else:
            return first_name
    elif username:
        return f"@{username}"
    else:
        return str(user_id)

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=data)
    except Exception as e:
        logger.error(f"Error sending message: {e}")

def get_updates(offset=None):
    url = f"{BASE_URL}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    try:
        response = requests.get(url, params=params)
        return response.json().get("result", [])
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return []

def handle_start(chat_id, user_name):
    welcome = f"""👋 Здравствуйте, {user_name}!

Добро пожаловать в бот управления сменами.

📅 **Доступные команды:**
/week - Посмотреть расписание на неделю
/shift ГГГГ-ММ-ДД 1 - Первая смена (9:30-16:30)
/shift ГГГГ-ММ-ДД 2 - Вторая смена (16:00-23:00)
/my_shifts - Мои смены
/cancel ГГГГ-ММ-ДД 1|2 - Отменить запись

📌 Пример: /shift 2026-04-28 1

Хорошего дня! ☀️"""
    send_message(chat_id, welcome)

def handle_week(chat_id):
    data = load_data()
    today = datetime.now().date()
    weekdays_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    
    msg = "📅 **Расписание смен на следующую неделю:**\n\n"
    
    for i in range(7):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        weekday = weekdays_ru[date.weekday()]
        
        shifts = data["shifts"].get(date_str, {"first": [], "second": []})
        
        first_list = shifts['first'] if shifts['first'] else ["— Никто не записан —"]
        second_list = shifts['second'] if shifts['second'] else ["— Никто не записан —"]
        
        first = ', '.join(first_list)
        second = ', '.join(second_list)
        
        msg += f"*{weekday} ({date_str})*\n"
        msg += f"🌅 Первая смена (9:30-16:30): {first}\n"
        msg += f"🌙 Вторая смена (16:00-23:00): {second}\n\n"
    
    send_message(chat_id, msg)

def handle_shift(chat_id, args, user):
    if len(args) != 2:
        send_message(chat_id, "📝 Использование: /shift ГГГГ-ММ-ДД 1|2\n\nПример: /shift 2026-04-28 1")
        return
    
    date_str = args[0]
    shift_num = args[1]
    
    # Get display name from user object
    display_name = get_display_name(user)
    
    # Validate date
    try:
        shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if shift_date < datetime.now().date():
            send_message(chat_id, "❌ Нельзя записаться на прошедшую дату!")
            return
        if shift_date > datetime.now().date() + timedelta(days=7):
            send_message(chat_id, "❌ Записывайтесь только на следующую неделю (максимум 7 дней вперёд)!")
            return
    except ValueError:
        send_message(chat_id, "❌ Неверный формат даты! Используйте ГГГГ-ММ-ДД\n\nПример: /shift 2026-04-28 1")
        return
    
    # Validate shift number
    if shift_num not in ["1", "2"]:
        send_message(chat_id, "❌ Смена должна быть 1 (первая) или 2 (вторая)")
        return
    
    data = load_data()
    if date_str not in data["shifts"]:
        data["shifts"][date_str] = {"first": [], "second": []}
    
    key = "first" if shift_num == "1" else "second"
    
    if display_name not in data["shifts"][date_str][key]:
        data["shifts"][date_str][key].append(display_name)
        save_data(data)
        shift_name = "первую смену (9:30-16:30)" if shift_num == "1" else "вторую смену (16:00-23:00)"
        send_message(chat_id, f"✅ {display_name}, вы записаны на {shift_name} на {date_str}")
    else:
        send_message(chat_id, f"❌ {display_name}, вы уже записаны на эту смену на {date_str}!")

def handle_my_shifts(chat_id, user):
    display_name = get_display_name(user)
    data = load_data()
    today = datetime.now().date()
    my_list = []
    
    for date_str, shifts in data["shifts"].items():
        try:
            shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if shift_date >= today:
                if display_name in shifts.get("first", []):
                    my_list.append(f"📅 {date_str}: Первая смена (9:30-16:30)")
                if display_name in shifts.get("second", []):
                    my_list.append(f"📅 {date_str}: Вторая смена (16:00-23:00)")
        except:
            pass
    
    if my_list:
        msg = "📋 **Ваши предстоящие смены:**\n\n" + "\n".join(my_list)
    else:
        msg = "📋 У вас нет запланированных смен."
    
    send_message(chat_id, msg)

def handle_cancel(chat_id, args, user):
    if len(args) != 2:
        send_message(chat_id, "📝 Использование: /cancel ГГГГ-ММ-ДД 1|2\n\nПример: /cancel 2026-04-28 1")
        return
    
    date_str = args[0]
    shift_num = args[1]
    display_name = get_display_name(user)
    
    data = load_data()
    key = "first" if shift_num == "1" else "second"
    
    if date_str in data["shifts"] and display_name in data["shifts"][date_str][key]:
        data["shifts"][date_str][key].remove(display_name)
        save_data(data)
        shift_name = "первой смены" if shift_num == "1" else "второй смены"
        send_message(chat_id, f"✅ {display_name}, вы отменены от {shift_name} на {date_str}")
    else:
        send_message(chat_id, f"❌ {display_name}, вы не записаны на эту смену на {date_str}!")

def handle_help(chat_id):
    help_text = """📋 **Команды бота управления сменами**

/start - Показать приветствие
/week - Расписание на следующую неделю
/shift ГГГГ-ММ-ДД 1 - Записаться на первую смену (9:30-16:30)
/shift ГГГГ-ММ-ДД 2 - Записаться на вторую смену (16:00-23:00)
/my_shifts - Показать мои смены
/cancel ГГГГ-ММ-ДД 1|2 - Отменить запись на смену
/help - Показать эту справку

📌 **Формат даты:** ГГГГ-ММ-ДД (например, 2026-04-28)

Примеры:
/shift 2026-04-28 1 - Запись на первую смену 28 апреля
/cancel 2026-04-28 1 - Отмена с первой смены 28 апреля"""
    
    send_message(chat_id, help_text)

def process_update(update):
    try:
        message = update.get("message")
        if not message:
            return
        
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        
        # Get the full user object
        user = message.get("from", {})
        user_name = user.get("first_name", "")
        
        if not text.startswith("/"):
            return
        
        parts = text.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if command == "/start":
            handle_start(chat_id, user_name)
        elif command == "/week":
            handle_week(chat_id)
        elif command == "/shift":
            handle_shift(chat_id, args, user)
        elif command == "/my_shifts":
            handle_my_shifts(chat_id, user)
        elif command == "/cancel":
            handle_cancel(chat_id, args, user)
        elif command == "/help":
            handle_help(chat_id)
        else:
            send_message(chat_id, "❌ Неизвестная команда. Используйте /help для списка команд.")
    except Exception as e:
        logger.error(f"Error processing update: {e}")

def run_bot():
    logger.info("🤖 Starting bot polling loop...")
    last_update_id = 0
    
    while True:
        try:
            updates = get_updates(last_update_id + 1)
            for update in updates:
                process_update(update)
                last_update_id = update["update_id"]
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        
        time.sleep(1)

def main():
    logger.info("🤖 Starting shift bot with HTTP server...")
    
    # Start web server in background thread
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    logger.info(f"✅ HTTP server started on port {os.environ.get('PORT', 10000)}")
    
    # Run bot (this blocks)
    run_bot()

if __name__ == "__main__":
    main()