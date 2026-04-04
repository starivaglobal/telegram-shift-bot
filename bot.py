import os
import json
import logging
from datetime import datetime, timedelta
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("NO TOKEN FOUND!")
    exit(1)

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
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

def send_message(chat_id, text):
    """Send a message to a user"""
    url = f"{BASE_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=data)
    except Exception as e:
        logger.error(f"Error sending message: {e}")

def get_updates(offset=None):
    """Get new updates from Telegram"""
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
/shift YYYY-MM-DD 1 - Первая смена (9:30-16:30)
/shift YYYY-MM-DD 2 - Вторая смена (16:00-23:00)
/my_shifts - Мои смены
/cancel YYYY-MM-DD 1|2 - Отменить запись

📌 Пример: /shift 2026-04-25 1"""
    send_message(chat_id, welcome)

def handle_week(chat_id):
    data = load_data()
    today = datetime.now().date()
    weekdays_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    
    msg = "📅 Расписание смен на следующую неделю:\n\n"
    
    for i in range(7):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        weekday = weekdays_ru[date.weekday()]
        
        shifts = data["shifts"].get(date_str, {"first": [], "second": []})
        
        first = ', '.join(shifts['first']) if shifts['first'] else "— Никто не записан —"
        second = ', '.join(shifts['second']) if shifts['second'] else "— Никто не записан —"
        
        msg += f"{weekday} ({date_str})\n"
        msg += f"🌅 Первая смена (9:30-16:30): {first}\n"
        msg += f"🌙 Вторая смена (16:00-23:00): {second}\n\n"
    
    send_message(chat_id, msg)

def handle_shift(chat_id, args, username):
    if len(args) != 2:
        send_message(chat_id, "📝 Использование: /shift YYYY-MM-DD 1|2")
        return
    
    date_str = args[0]
    shift_num = args[1]
    
    # Validate date
    try:
        shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if shift_date < datetime.now().date():
            send_message(chat_id, "❌ Нельзя записаться на прошедшую дату!")
            return
        if shift_date > datetime.now().date() + timedelta(days=7):
            send_message(chat_id, "❌ Записывайтесь только на следующую неделю!")
            return
    except ValueError:
        send_message(chat_id, "❌ Неверный формат даты! Используйте ГГГГ-ММ-ДД")
        return
    
    if shift_num not in ["1", "2"]:
        send_message(chat_id, "❌ Смена должна быть 1 или 2")
        return
    
    data = load_data()
    if date_str not in data["shifts"]:
        data["shifts"][date_str] = {"first": [], "second": []}
    
    key = "first" if shift_num == "1" else "second"
    full_name = f"@{username}" if username else str(chat_id)
    
    if full_name not in data["shifts"][date_str][key]:
        data["shifts"][date_str][key].append(full_name)
        save_data(data)
        shift_name = "первую смену (9:30-16:30)" if shift_num == "1" else "вторую смену (16:00-23:00)"
        send_message(chat_id, f"✅ Вы записаны на {shift_name} на {date_str}")
    else:
        send_message(chat_id, "❌ Вы уже записаны на эту смену!")

def handle_my_shifts(chat_id, username):
    full_name = f"@{username}" if username else str(chat_id)
    data = load_data()
    today = datetime.now().date()
    my_list = []
    
    for date_str, shifts in data["shifts"].items():
        try:
            shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if shift_date >= today:
                if full_name in shifts.get("first", []):
                    my_list.append(f"📅 {date_str}: Первая смена (9:30-16:30)")
                if full_name in shifts.get("second", []):
                    my_list.append(f"📅 {date_str}: Вторая смена (16:00-23:00)")
        except:
            pass
    
    if my_list:
        msg = "📋 Ваши предстоящие смены:\n\n" + "\n".join(my_list)
    else:
        msg = "📋 У вас нет запланированных смен."
    
    send_message(chat_id, msg)

def handle_cancel(chat_id, args, username):
    if len(args) != 2:
        send_message(chat_id, "📝 Использование: /cancel YYYY-MM-DD 1|2")
        return
    
    date_str = args[0]
    shift_num = args[1]
    full_name = f"@{username}" if username else str(chat_id)
    
    data = load_data()
    key = "first" if shift_num == "1" else "second"
    
    if date_str in data["shifts"] and full_name in data["shifts"][date_str][key]:
        data["shifts"][date_str][key].remove(full_name)
        save_data(data)
        shift_name = "первой смены" if shift_num == "1" else "второй смены"
        send_message(chat_id, f"✅ Вы отменены от {shift_name} на {date_str}")
    else:
        send_message(chat_id, "❌ Вы не записаны на эту смену!")

def process_update(update):
    """Process a single update from Telegram"""
    try:
        message = update.get("message")
        if not message:
            return
        
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        username = message["from"].get("username", "")
        user_name = message["from"].get("first_name", "")
        
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
            handle_shift(chat_id, args, username)
        elif command == "/my_shifts":
            handle_my_shifts(chat_id, username)
        elif command == "/cancel":
            handle_cancel(chat_id, args, username)
        else:
            send_message(chat_id, "Неизвестная команда. Используйте /help")
    except Exception as e:
        logger.error(f"Error processing update: {e}")

def main():
    logger.info("🤖 Starting shift bot (direct API mode)...")
    
    last_update_id = 0
    
    while True:
        try:
            updates = get_updates(last_update_id + 1)
            for update in updates:
                process_update(update)
                last_update_id = update["update_id"]
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        
        import time
        time.sleep(1)

if __name__ == "__main__":
    main()