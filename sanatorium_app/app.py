import streamlit as st
import sqlite3
import pandas as pd
import requests
import uuid
from datetime import datetime, timedelta

# Настройка страницы
st.set_page_config(page_title="Санаторий Олтин Сой", layout="wide")

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
            requests.post(url, json=payload, timeout=5)
        except Exception:
            pass

# Работа с БД
def run_query(query, params=(), is_select=True):
    conn = sqlite3.connect("sanatorium.db", timeout=15)
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if is_select:
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            df = pd.DataFrame(data, columns=columns)
            return df
        else:
            conn.commit()
            return True
    except Exception as e:
        if is_select:
            return pd.DataFrame()
        return False
    finally:
        conn.close()

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

# Инициализация БД
def init_db():
    run_query('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL,
            room TEXT DEFAULT '-',
            package TEXT DEFAULT 'Бесплатный',
            complaints TEXT DEFAULT '-',
            check_in_date TEXT DEFAULT '-',
            check_out_date TEXT DEFAULT '-',
            duration_days INTEGER DEFAULT 0,
            guests_count INTEGER DEFAULT 1,
            total_cost INTEGER DEFAULT 0,
            birth_year TEXT DEFAULT '-',
            passport_series TEXT DEFAULT '-',
            id_type TEXT DEFAULT 'Паспорт',
            payment_method TEXT DEFAULT '-'
        )
    ''', is_select=False)

    run_query('''
        CREATE TABLE IF NOT EXISTS checkout_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            room TEXT,
            check_in_date TEXT,
            check_out_date TEXT,
            duration_days TEXT,
            guests_count TEXT,
            total_cost TEXT,
            payment_method TEXT,
            archive_date TEXT,
            comment TEXT DEFAULT '-'
        )
    ''', is_select=False)

    run_query('''
        CREATE TABLE IF NOT EXISTS rooms (
            room_number TEXT NOT NULL,
            corpus TEXT NOT NULL,
            floor TEXT NOT NULL,
            status TEXT DEFAULT 'Свободно',
            price_type TEXT DEFAULT 'Стандарт',
            price_per_day INTEGER DEFAULT 0,
            PRIMARY KEY (room_number, price_type)
        )
    ''', is_select=False)

    run_query('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_phone TEXT,
            doctor_name TEXT,
            procedure_name TEXT,
            date_time TEXT,
            status TEXT DEFAULT 'SCHEDULED',
            medical_notes TEXT DEFAULT '-'
        )
    ''', is_select=False)

    # Авто-добавление колонок при обновлении версий
    for col, definition in {
        "guests_count": "INTEGER DEFAULT 1",
        "birth_year": "TEXT DEFAULT '-'",
        "passport_series": "TEXT DEFAULT '-'",
        "id_type": "TEXT DEFAULT 'Паспорт'",
        "payment_method": "TEXT DEFAULT '-'",
        "check_out_date": "TEXT DEFAULT '-'"
    }.items():
        run_query(f"ALTER TABLE users ADD COLUMN {col} {definition}", is_select=False)

    # Дефолтный админ
    run_query("INSERT OR IGNORE INTO users (name, phone, role) VALUES ('Рустам (Администратор)', '+998973208668', 'Admin')", is_select=False)

    # Первоначальное наполнение комнат (если пустая БД)
    rooms_count_df = run_query("SELECT COUNT(*) as count FROM rooms")
    rooms_count = rooms_count_df['count'][0] if (rooms_count_df is not None and not rooms_count_df.empty) else 0
    if rooms_count == 0:
        rooms_data = []
        for i in range(1, 14):
            rooms_data.append((f"0{i}" if i < 10 else f"{i}", "Корпус 1", "1", "Свободно", "Стандарт", 170000))
        for i in range(1, 6):
            rooms_data.append((f"0{i}", "Корпус 1", "2", "Свободно", "Полу-Люкс", 200000))
        for i in range(1, 9):
            rooms_data.append((f"0{i}", "Корпус 2", "3", "Свободно", "Люкс", 250000))
        for r_num, corp, flr, stat, p_type, p_day in rooms_data:
            run_query("INSERT OR IGNORE INTO rooms (room_number, corpus, floor, status, price_type, price_per_day) VALUES (?, ?, ?, ?, ?, ?)", (r_num, corp, flr, stat, p_type, p_day), is_select=False)

init_db()

# --- ФУНКЦИЯ ДЛЯ УВЕДОМЛЕНИЙ ЗА ДЕНЬ ДО ВЫЕЗДА ---
if 'notified_today' not in st.session_state:
    st.session_state['notified_today'] = set()

def check_upcoming_checkouts():
    # Завтрашняя дата
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    # Ищем пациентов, которые должны выехать завтра
    tomorrow_departures = run_query("SELECT name, room, phone, check_out_date FROM users WHERE role='Пациент' AND room != '-'")
    if tomorrow_departures is not None and not tomorrow_departures.empty:
        for _, row in tomorrow_departures.iterrows():
            # Приведем к единому формату даты для сравнения
            try:
                db_date = datetime.strptime(str(row['check_out_date']).strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
            except:
                db_date = str(row['check_out_date']).strip()
                
            if db_date == tomorrow_str:
                p_id = f"{row['phone']}_{tomorrow_str}"
                if p_id not in st.session_state['notified_today']:
                    msg = f"🔔 *Внимание:* {row['name']} из палаты {row['room']} уходит завтра ({tomorrow_str})."
                    send_telegram_notification(msg)
                    st.session_state['notified_today'].add(p_id)

check_upcoming_checkouts()

# Глобальные сессии
@st.cache_resource(ttl=86400)
def get_global_sessions(): return {}
global_sessions = get_global_sessions()

if 'session_token' not in st.session_state:
    st.session_state['session_token'] = str(uuid.uuid4())
token = st.session_state['session_token']

if 'logged_in_user' not in st.session_state:
    st.session_state['logged_in_user'] = global_sessions.get(token, None)

if st.session_state['logged_in_user'] is not None:
    saved_phone = st.session_state['logged_in_user']['phone']
    user_refresh = run_query("SELECT * FROM users WHERE phone = ?", (saved_phone,))
    if user_refresh is not None and not user_refresh.empty:
        st.session_state['logged_in_user'] = user_refresh.iloc[0]
        global_sessions[token] = user_refresh.iloc[0]

if 'show_registration' not in st.session_state: st.session_state['show_registration'] = False
if 'reg_phone' not in st.session_state: st.session_state['reg_phone'] = ""

# Вспомогательная функция: подсчет занятых мест в каждой палате
def get_room_occupancy():
    # Считаем сумму гостей (guests_count) для каждой уникальной палаты
    occupancy = {}
    active_users = run_query("SELECT room, guests_count FROM users WHERE role='Пациент' AND room != '-'")
    if active_users is not None and not active_users.empty:
        for _, row in active_users.iterrows():
            r_name = row['room']
            g_c = clean_numeric(row['guests_count'])
            occupancy[r_name] = occupancy.get(r_name, 0) + g_c
    return occupancy

# --- СТАРТОВАЯ СТРАНИЦА ---
if st.session_state['logged_in_user'] is None:
    st.title("🌟 Санаторий «Олтин Сой»")
    st.subheader("Многоместная система бронирования палат")
    
    if not st.session_state['show_registration']:
        st.info("### 📱 Авторизация")
        with st.form("login_form"):
            phone_input = st.text_input("Номер телефона (Или оставьте пустым для входа как Гость)").strip()
            admin_password = st.text_input("🔑 Пароль администратора (Для Рустама)", type="password")
            sms_confirm = st.checkbox("Согласен с правилами обработки данных", value=True)
            submit_login = st.form_submit_button("🚀 Войти")
            
        if submit_login:
            final_phone = phone_input if phone_input else f"Гость_{str(uuid.uuid4())[:8]}"
            if final_phone == "+998973208668" and admin_password != "XojiOna62":
                st.error("Неверный пароль администратора!")
            else:
                user_df = run_query("SELECT * FROM users WHERE phone = ?", (final_phone,))
                if user_df is not None and not user_df.empty:
                    st.session_state['logged_in_user'] = user_df.iloc[0]
                    global_sessions[token] = user_df.iloc[0]
                    st.rerun()
                else:
                    st.session_state['show_registration'] = True
                    st.session_state['reg_phone'] = phone_input
                    st.rerun()
        if st.button("📝 Регистрация нового аккаунта"):
            st.session_state['show_registration'] = True
            st.rerun()
    else:
        st.info("### 📝 Регистрация нового пациента")
        with st.form("reg_form"):
            p_phone = st.text_input("Ваш номер телефона (Не обязательно)", value=st.session_state['reg_phone'])
            new_name = st.text_input("Имя, Фамилия *")
            new_birth = st.text_input("Год рождения")
            new_id_type = st.selectbox("Тип документа", ["Паспорт", "Водительские права"])
            new_passport = st.text_input("Серия и номер документа")
            new_complaint = st.text_area("Жалобы при поступлении")
            if st.form_submit_button("Зарегистрироваться"):
                if not new_name:
                    st.error("Укажите ваше имя!")
                else:
                    final_reg_phone = p_phone.strip() if p_phone.strip() else f"NoPhone_{str(uuid.uuid4())[:8]}"
                    run_query('''
                        INSERT INTO users (name, phone, role, complaints, birth_year, passport_series, id_type) 
                        VALUES (?, ?, 'Пациент', ?, ?, ?, ?)
                    ''', (new_name, final_reg_phone, new_complaint, new_birth, new_passport, new_id_type), is_select=False)
                    
                    user_res = run_query("SELECT * FROM users WHERE phone = ?", (final_reg_phone,))
                    if user_res is not None and not user_res.empty:
                        st.session_state['show_registration'] = False
                        st.session_state['logged_in_user'] = user_res.iloc[0]
                        global_sessions[token] = user_res.iloc[0]
                        send_telegram_notification(f"🔔 *Новый гость:* {new_name} ({p_phone if p_phone else 'Без номера'})")
                        st.rerun()

else:
    current_user = st.session_state['logged_in_user']
    role = current_user['role']
    
    st.sidebar.title("📱 Аккаунт")
    st.sidebar.write(f"ФИО: **{current_user['name']}**")
    st.sidebar.write(f"Тел: `{current_user['phone']}`")
    if st.sidebar.button("🚪 Выйти", use_container_width=True):
        st.session_state['logged_in_user'] = None
        if token in global_sessions: del global_sessions[token]
        st.rerun()

    # Считываем текущую занятость мест в палатах
    room_occupancy = get_room_occupancy()

    # --- АДМИНИСТРАТОР (РУСТАМ) ---
    if role == 'Admin':
        st.title("💼 Панель Администратора: Рустам")
        t1, t2, t3, t4, t5, t6 = st.tabs(["📊 Текущий обзор", "👥 Регистрация и Заселение", "🏨 Сетка палат (4 места)", "📅 Назначение процедур", "📤 Выписка и Семьи", "📅 Отчеты за год"])

        with t1:
            st.subheader("Список проживающих пациентов")
            p_df = run_query('''
                SELECT name as 'ФИО', phone as 'Телефон/ID', room as 'Палата', 
                       check_in_date as 'Дата заезда', check_out_date as 'Дата выезда', 
                       guests_count as 'Гостей на брони', total_cost as 'Личная стоимость (сум)' 
                FROM users WHERE role='Пациент' AND room != '-'
            ''')
            if p_df is not None and not p_df.empty:
                st.dataframe(p_df, use_container_width=True)
            else:
                st.info("Нет активно заселенных пациентов.")

        with t2:
            st.subheader("👥 Регистрация нового человека с подселением")
            # Фильтруем палаты: выводим те, где занято менее 4 мест
            all_db_rooms = run_query("SELECT room_number, price_type, price_per_day FROM rooms")
            room_options = []
            if all_db_rooms is not None and not all_db_rooms.empty:
                for _, r in all_db_rooms.iterrows():
                    r_full_name = f"{r['room_number']} ({r['price_type']})"
                    occupied_spots = room_occupancy.get(r_full_name, 0)
                    free_spots = 4 - occupied_spots
                    if free_spots > 0:
                        room_options.append(f"{r['room_number']} ({r['price_type']} - {r['price_per_day']} сум/сутки) [Свободно мест: {free_spots} из 4]")
            
            with st.form("admin_multispot_reg_form"):
                adm_name = st.text_input("ФИО Пациента *")
                adm_phone = st.text_input("Номер телефона (Не обязательно)")
                adm_birth = st.text_input("Год рождения")
                adm_passport = st.text_input("Серия/Номер документа")
                
                st.markdown("#### 🏨 Параметры бронирования:")
                need_booking = st.checkbox("Заселить в палату прямо сейчас?", value=True)
                adm_room = st.selectbox("Доступные палаты (свободно хотя бы 1 из 4 мест)", room_options if room_options else ["Нет свободных мест во всем санатории"])
                adm_in_date = st.date_input("Дата заезда", value=datetime.now().date())
                adm_out_date = st.date_input("Дата выезда (До какого числа)", value=datetime.now().date() + timedelta(days=7))
                adm_guests = st.number_input("Сколько человек заселяется по этой брони? (до 4)", min_value=1, max_value=4, value=1)
                adm_pay = st.selectbox("Способ оплаты", ["Полностью", "Частично"])
                
                if st.form_submit_button("🚀 Зарегистрировать и заселить"):
                    if not adm_name:
                        st.error("ФИО обязательно для заполнения!")
                    elif need_booking and not room_options:
                        st.error("Нет свободных комнат!")
                    else:
                        final_adm_phone = adm_phone.strip() if adm_phone.strip() else f"NoPhone_{str(uuid.uuid4())[:8]}"
                        
                        room_field = '-'
                        in_date_str = '-'
                        out_date_str = '-'
                        days = 0
                        cost = 0
                        
                        if need_booking and room_options and adm_room != "Нет свободных мест во всем санатории":
                            # Вытаскиваем чистые номер и категорию комнаты
                            raw_room_part = adm_room.split(" [")[0] # "01 (Стандарт - 170000 сум/сутки)"
                            r_num = raw_room_part.split(" (")[0]
                            r_type = raw_room_part.split(" (")[1].split(" - ")[0]
                            r_full_name = f"{r_num} ({r_type})"
                            
                            # Проверяем лимит мест
                            occupied_now = room_occupancy.get(r_full_name, 0)
                            if occupied_now + int(adm_guests) > 4:
                                st.error(f"Невозможно заселить {adm_guests} чел. В палате {r_full_name} свободно только {4 - occupied_now} мест!")
                                st.stop()
                            
                            days = (adm_out_date - adm_in_date).days
                            if days <= 0: days = 1
                            
                            room_info = run_query("SELECT price_per_day FROM rooms WHERE room_number = ? AND price_type = ?", (r_num, r_type))
                            price = clean_numeric(room_info['price_per_day'][0]) if not room_info.empty else 0
                            cost = price * days * int(adm_guests)
                            
                            room_field = r_full_name
                            in_date_str = str(adm_in_date)
                            out_date_str = str(adm_out_date)
                            
                            # Обновим статус палаты на "Занято", если заняты все 4 места
                            new_total_occ = occupied_now + int(adm_guests)
                            new_status = "Занято" if new_total_occ >= 4 else "Частично занято"
                            run_query("UPDATE rooms SET status = ? WHERE room_number = ? AND price_type = ?", (new_status, r_num, r_type), is_select=False)
                        
                        run_query('''
                            INSERT INTO users (name, phone, role, room, check_in_date, check_out_date, duration_days, guests_count, total_cost, birth_year, passport_series, payment_method)
                            VALUES (?, ?, 'Пациент', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (adm_name, final_adm_phone, room_field, in_date_str, out_date_str, days, int(adm_guests), cost, adm_birth, adm_passport, adm_pay), is_select=False)
                        
                        send_telegram_notification(f"🏨 *Новое заселение:* {adm_name}\n🛏 Палата: {room_field}\n👥 Мест занято: {adm_guests}\n📅 Срок до: {out_date_str}\n💰 Оплата: {cost:,} сум")
                        st.success("Пациент успешно сохранен и подселен!")
                        st.rerun()

        with t3:
            st.subheader("🏨 Состояние мест в каждой палате (4-местная сетка)")
            rooms_grid = run_query("SELECT room_number, price_type, price_per_day, corpus, floor FROM rooms")
            if rooms_grid is not None and not rooms_grid.empty:
                grid_data = []
                for _, r in rooms_grid.iterrows():
                    r_full = f"{r['room_number']} ({r['price_type']})"
                    occupied_spots = room_occupancy.get(r_full, 0)
                    free_spots = 4 - occupied_spots
                    
                    # Кто именно сейчас живет в этой палате
                    living_here = run_query("SELECT name, phone, guests_count FROM users WHERE role='Пациент' AND room=?", (r_full,))
                    guests_list_str = []
                    if living_here is not None and not living_here.empty:
                        for _, u in living_here.iterrows():
                            guests_list_str.append(f"{u['name']} ({u['guests_count']} мест)")
                    guests_display = ", ".join(guests_list_str) if guests_list_str else "Никого нет"
                    
                    grid_data.append({
                        "Палата": r['room_number'],
                        "Тип": r['price_type'],
                        "Цена/Сутки": f"{r['price_per_day']:,} сум",
                        "Занято мест": f"{occupied_spots} из 4",
                        "Свободно мест": free_spots,
                        "Текущие жильцы": guests_display,
                        "Корпус/Этаж": f"{r['corpus']}, {r['floor']} этаж"
                    })
                st.dataframe(pd.DataFrame(grid_data), use_container_width=True)

        with t4:
            st.subheader("📅 Назначение лечебных процедур")
            patients = run_query("SELECT phone, name FROM users WHERE role='Пациент'")
            p_opts = [f"{r['name']} ({r['phone']})" for _, r in patients.iterrows()] if (patients is not None and not patients.empty) else ["Нет зарегистрированных пациентов"]
            
            with st.form("proc_assign_form"):
                sel_p = st.selectbox("Выберите пациента", p_opts)
                proc = st.selectbox("Медицинская процедура", ["Массаж", "Грязевая ванна", "Ингаляция", "Иглоукалывание"])
                dt = st.text_input("Желаемое время", "Завтра, 10:30")
                if st.form_submit_button("Назначить процедуру"):
                    if sel_p != "Нет зарегистрированных пациентов":
                        ph = sel_p.split("(")[-1].replace(")", "")
                        run_query("INSERT INTO appointments (patient_phone, doctor_name, procedure_name, date_time) VALUES (?, 'Сапартошев А.', ?, ?)", (ph, proc, dt), is_select=False)
                        st.success("Успешно добавлено в расписание!")

        with t5:
            st.subheader("📤 Оформление выписки (Освобождение койко-мест)")
            active_p = run_query("SELECT * FROM users WHERE role='Пациент' AND room != '-'")
            if active_p is not None and not active_p.empty:
                p_choose = st.selectbox("Выберите человека для выписки", [f"{r['name']} ({r['phone']}) - {r['room']} [Занимает мест: {r['guests_count']}]" for _, r in active_p.iterrows()])
                chosen_phone = p_choose.split("(")[1].split(")")[0]
                p_data = run_query("SELECT * FROM users WHERE phone = ?", (chosen_phone,)).iloc[0]
                
                g_count = clean_numeric(p_data['guests_count'])
                
                st.markdown(f"**Выписывается пациент:** {p_data['name']}")
                st.info(f"Палата: {p_data['room']} | Занимает мест: {g_count} | Общая начисленная сумма: {clean_numeric(p_data['total_cost']):,} сум")
                
                if st.button("🚪 Выписать и отправить в Отчёты"):
                    # Сохраняем в годовой архив (сохраняем инфу о заработке)
                    run_query('''
                        INSERT INTO checkout_archive (name, phone, room, check_in_date, check_out_date, duration_days, guests_count, total_cost, payment_method, archive_date, comment)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Автовыписка')
                    ''', (p_data['name'], p_data['phone'], p_data['room'], p_data['check_in_date'], p_data['check_out_date'], str(p_data['duration_days']), str(g_count), str(p_data['total_cost']), p_data['payment_method'], str(datetime.now().date())), is_select=False)
                    
                    # Освобождаем места у пользователя
                    run_query("UPDATE users SET room='-', check_in_date='-', check_out_date='-', duration_days=0, total_cost=0, guests_count=1 WHERE phone=?", (chosen_phone,), is_select=False)
                    
                    # Проверяем общую наполненность палаты после выезда этого человека
                    r_full_name = p_data['room']
                    try:
                        r_num = r_full_name.split(" (")[0]
                        r_type = r_full_name.split(" (")[1].replace(")", "")
                        
                        # Пересчитываем сколько мест теперь занято в этой комнате
                        updated_occupancy = get_room_occupancy()
                        still_occupied = updated_occupancy.get(r_full_name, 0)
                        
                        new_status = "Свободно" if still_occupied == 0 else "Частично занято"
                        run_query("UPDATE rooms SET status = ? WHERE room_number = ? AND price_type = ?", (new_status, r_num, r_type), is_select=False)
                    except: pass
                    
                    send_telegram_notification(f"📤 *Успешный выезд:* {p_data['name']}\nПалата: {r_full_name}\nЗаработано: {clean_numeric(p_data['total_cost']):,} сум")
                    st.success(f"{p_data['name']} успешно выписан, данные перенесены в архив годовой отчетности!")
                    st.rerun()
            else:
                st.info("Нет активных заселенных пациентов для выписки.")

        with t6:
            st.subheader("📅 Отчеты за год (Выписанные пациенты и Заработок)")
            arch = run_query("SELECT id, name as 'ФИО', phone as 'Телефон/ID', room as 'Палата', check_in_date as 'Заезд', check_out_date as 'Выезд', duration_days as 'Дней', guests_count as 'Мест', total_cost as 'Заработано (сум)', archive_date as 'Дата выписки' FROM checkout_archive")
            
            if arch is not None and not arch.empty:
                # Автоматическое суммирование всех доходов
                arch['Заработано (сум)'] = arch['Заработано (сум)'].apply(clean_numeric)
                total_earnings = arch['Заработано (сум)'].sum()
                
                st.metric(label="💰 ОБЩИЙ ЗАРАБОТОК С ВЫПИСАННЫХ КЛИЕНТОВ", value=f"{total_earnings:,} сум")
                st.dataframe(arch, use_container_width=True)
                
                # --- ПАНЕЛЬ "КОРЗИНА" ДЛЯ УДАЛЕНИЯ ОШИБОЧНЫХ ЛЮДЕЙ ---
                st.markdown("---")
                st.markdown("### 🗑️ Панель «Корзина»")
                st.caption("Здесь вы можете безвозвратно удалить ошибочно выписанных людей из отчетов за год.")
                
                delete_options = [f"{row['ФИО']} ({row['Телефон/ID']}) - {row['Заработано (сум)']} сум [ID: {row['id']}]" for _, row in arch.iterrows()]
                selected_for_delete = st.selectbox("Выберите запись для удаления из архива", delete_options)
                
                if st.button("❌ Безвозвратно удалить из отчетов"):
                    selected_id = selected_for_delete.split("[ID: ")[-1].replace("]", "")
                    success = run_query("DELETE FROM checkout_archive WHERE id = ?", (selected_id,), is_select=False)
                    if success:
                        st.success("Запись успешно удалена из архива отчетов!")
                        st.rerun()
            else:
                st.metric(label="💰 ОБЩИЙ ЗАРАБОТОК С ВЫПИСАННЫХ КЛИЕНТОВ", value="0 сум")
                st.info("Архив годовых отчетов пока пуст.")

    # --- КАБИНЕТ ПАЦИЕНТА ---
    elif role == 'Пациент':
        st.title(f"👤 Личный Кабинет Пациента: {current_user['name']}")
        p_tab1, p_tab2 = st.tabs(["🏨 Моя бронь и Свободные места", "📅 Мои лечебные процедуры"])
        
        with p_tab1:
            if current_user['room'] == '-':
                st.write("#### Доступные палаты для онлайн-подселения (до 4 человек на палату)")
                all_db_rooms = run_query("SELECT room_number, price_type, price_per_day FROM rooms")
                client_options = []
                grid_client_data = []
                
                if all_db_rooms is not None and not all_db_rooms.empty:
                    for _, r in all_db_rooms.iterrows():
                        r_full_name = f"{r['room_number']} ({r['price_type']})"
                        occupied_spots = room_occupancy.get(r_full_name, 0)
                        free_spots = 4 - occupied_spots
                        
                        if free_spots > 0:
                            client_options.append(f"{r['room_number']} ({r['price_type']} - {r['price_per_day']} сум/сутки) [Свободно мест: {free_spots}]")
                            grid_client_data.append({
                                "Номер": r['room_number'],
                                "Тип": r['price_type'],
                                "Цена за сутки": f"{r['price_per_day']:,} сум",
                                "Свободно мест": f"{free_spots} из 4"
                            })
                
                if grid_client_data:
                    st.dataframe(pd.DataFrame(grid_client_data), use_container_width=True)
                    
                    with st.form("client_self_booking"):
                        r_sel = st.selectbox("Выберите свободную палату", client_options)
                        in_d = st.date_input("Дата заселения")
                        out_d = st.date_input("До какого числа (Дата выезда)", value=datetime.now().date() + timedelta(days=7))
                        gst = st.number_input("Сколько мест вы бронируете? (для себя/семьи)", min_value=1, max_value=4, value=1)
                        
                        if st.form_submit_button("🔒 Подтвердить бронь"):
                            raw_room_part = r_sel.split(" [")[0]
                            r_num = raw_room_part.split(" (")[0]
                            r_type = raw_room_part.split(" (")[1].split(" - ")[0]
                            r_full_name = f"{r_num} ({r_type})"
                            
                            occupied_now = room_occupancy.get(r_full_name, 0)
                            if occupied_now + int(gst) > 4:
                                st.error(f"Извините, в этой палате осталось только {4 - occupied_now} свободных мест!")
                                st.stop()
                                
                            days = (out_d - in_d).days
                            if days <= 0: days = 1
                            
                            room_info = run_query("SELECT price_per_day FROM rooms WHERE room_number = ? AND price_type = ?", (r_num, r_type))
                            price = clean_numeric(room_info['price_per_day'][0]) if not room_info.empty else 0
                            cost = price * days * int(gst)
                            
                            run_query('''
                                UPDATE users SET room=?, check_in_date=?, check_out_date=?, duration_days=?, guests_count=?, total_cost=? WHERE phone=?
                            ''', (r_full_name, str(in_d), str(out_d), days, int(gst), cost, current_user['phone']), is_select=False)
                            
                            new_total_occ = occupied_now + int(gst)
                            new_status = "Занято" if new_total_occ >= 4 else "Частично занято"
                            run_query("UPDATE rooms SET status = ? WHERE room_number = ? AND price_type = ?", (new_status, r_num, r_type), is_select=False)
                            
                            send_telegram_notification(f"🏨 *Новая онлайн бронь:* {current_user['name']}\nПалата: {r_full_name}\nМест: {gst}\nВыезд до: {out_d}")
                            st.success("Успешно забронировано!")
                            st.rerun()
                else:
                    st.info("Извините, в данный момент свободных мест в санатории нет.")
            else:
                st.success(f"Вы успешно проживаете в палате: **{current_user['room']}**")
                st.info(f"📅 Срок: с `{current_user['check_in_date']}` до `{current_user['check_out_date']}`")

        with p_tab2:
            st.write("### Ваше медицинское расписание")
            my_appointments = run_query("SELECT doctor_name as 'Врач', procedure_name as 'Процедура', date_time as 'Дата и время' FROM appointments WHERE patient_phone = ?", (current_user['phone'],))
            if my_appointments is not None and not my_appointments.empty:
                st.dataframe(my_appointments, use_container_width=True)
            else:
                st.info("Вам пока не назначено ни одной процедуры.")
