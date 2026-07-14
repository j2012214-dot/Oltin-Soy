import sqlite3
import requests
from datetime import datetime

# Конфигурация Telegram-уведомлений
TELEGRAM_TOKEN = "8622312789:AAGJFYwZ88GEojsn1TwX8KYho3QxAs2P9Ss"
TELEGRAM_CHAT_ID = "-1003990319485"

def send_telegram_notification(text):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Ошибка отправки Telegram: {e}")

def clean_numeric(val):
    if val is None:
        return 0
    s = str(val).strip()
    if ',' in s:
        s = s.split(',')[0]
    s = ''.join(c for c in s if c.isdigit() or c == '.')
    try:
        return int(float(s)) if s else 0
    except:
        return 0

def get_room_occupancy(cursor):
    # Считаем сумму гостей для каждой уникальной палаты
    cursor.execute("SELECT room, guests_count FROM users WHERE role='Пациент' AND room != '-'")
    rows = cursor.fetchall()
    occupancy = {}
    for room, guests_count in rows:
        g_c = clean_numeric(guests_count)
        occupancy[room] = occupancy.get(room, 0) + g_c
    return occupancy

def run_auto_checkout():
    # Подключаемся к локальной базе данных
    conn = sqlite3.connect("C:\\Users\\user\\Desktop\\sanatorium_app\\sanatorium.db")
    cursor = conn.cursor()
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"Запуск автовыписки. Сегодняшняя дата: {today_str}")
    
    # 1. Находим пациентов, у которых дата выезда наступила (сегодня или раньше) и они еще в палате
    cursor.execute("SELECT * FROM users WHERE role='Пациент' AND room != '-'")
    columns = [desc[0] for desc in cursor.description]
    all_active = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    checkout_count = 0
    
    for p in all_active:
        try:
            # Парсим дату выезда
            p_out_date = str(p['check_out_date']).strip()
            # Проверяем формат (должен быть YYYY-MM-DD)
            db_date = datetime.strptime(p_out_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            # Если дата в базе записана неверно, пропускаем её, чтобы избежать ошибок автоматики
            continue
            
        # Если дата выезда совпадает с сегодняшним днем или уже прошла (в случае если компьютер не включали в день выезда)
        if db_date <= today_str:
            print(f"Выписываем: {p['name']} из палаты {p['room']}")
            
            # Сохраняем в архив
            cursor.execute('''
                INSERT INTO checkout_archive (name, phone, room, check_in_date, check_out_date, duration_days, guests_count, total_cost, payment_method, archive_date, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Автоматическая выписка по сроку')
            ''', (p['name'], p['phone'], p['room'], p['check_in_date'], p['check_out_date'], str(p['duration_days']), str(p['guests_count']), str(p['total_cost']), p['payment_method'], today_str))
            
            # Сбрасываем данные палаты у пользователя
            cursor.execute("UPDATE users SET room='-', check_in_date='-', check_out_date='-', duration_days=0, total_cost=0, guests_count=1 WHERE phone=?", (p['phone'],))
            
            # Пересчитываем статус комнаты
            r_full_name = p['room']
            try:
                r_num = r_full_name.split(" (")[0]
                r_type = r_full_name.split(" (")[1].replace(")", "")
                
                # Считаем текущую занятость после сброса
                occupancy = get_room_occupancy(cursor)
                still_occupied = occupancy.get(r_full_name, 0)
                
                new_status = "Свободно" if still_occupied == 0 else "Частично занято"
                cursor.execute("UPDATE rooms SET status = ? WHERE room_number = ? AND price_type = ?", (new_status, r_num, r_type))
            except Exception as e:
                print(f"Ошибка пересчета статуса комнаты {r_full_name}: {e}")
                
            # Отправляем уведомление
            send_telegram_notification(f"📤 *Фоновая автовыписка:* {p['name']}\nПалата: {r_full_name}\nСрок проживания окончен. Начислено: {clean_numeric(p['total_cost']):,} сум.")
            checkout_count += 1
            
    conn.commit()
    conn.close()
    print(f"Автовыписка завершена. Выписано человек: {checkout_count}")

if __name__ == "__main__":
    run_auto_checkout()
