import streamlit as st
import sqlite3
import pandas as pd
import requests
import uuid
from io import BytesIO
from datetime import datetime, timedelta

st.set_page_config(page_title="Санаторий Олтин Сой", layout="wide")

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

def run_query(query, params=(), is_select=True):
    conn = sqlite3.connect("sanatorium.db")
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
        error_msg = str(e).lower()
        if "duplicate column" in error_msg or "already exists" in error_msg:
            return True
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
            payment_method TEXT DEFAULT '-',
            guest_durations TEXT DEFAULT ''
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

    for col, definition in {
        "guests_count": "INTEGER DEFAULT 1",
        "birth_year": "TEXT DEFAULT '-'",
        "passport_series": "TEXT DEFAULT '-'",
        "id_type": "TEXT DEFAULT 'Паспорт'",
        "payment_method": "TEXT DEFAULT '-'",
        "check_out_date": "TEXT DEFAULT '-'",
        "guest_durations": "TEXT DEFAULT ''"
    }.items():
        run_query(f"ALTER TABLE users ADD COLUMN {col} {definition}", is_select=False)

    run_query("INSERT OR IGNORE INTO users (name, phone, role) VALUES ('Рустам (Администратор)', '+998973208668', 'Admin')", is_select=False)

    rooms_count_df = run_query("SELECT COUNT(*) as count FROM rooms")
    rooms_count = rooms_count_df['count'][0] if (rooms_count_df is not None and not rooms_count_df.empty) else 0
    if rooms_count == 0:
        rooms_data = []
        for i in range(1, 14):
            rooms_data.append((f"0{i}" if i < 10 else f"{i}", "Корпус 1", "1", "Свободно", "Стандарт", 170000))
        for i in range(1, 6):
            rooms_data.append((f"0{i}", "Корпус 1", "2", "Свободно", "Полу-Люкс", 200000))
        for i in range(1, 8):
            rooms_data.append((f"0{i}", "Корпус 2", "3", "Свободно", "Люкс", 250000))
        for r_num, corp, flr, stat, p_type, p_day in rooms_data:
            run_query("INSERT OR IGNORE INTO rooms (room_number, corpus, floor, status, price_type, price_per_day) VALUES (?, ?, ?, ?, ?, ?)", (r_num, corp, flr, stat, p_type, p_day), is_select=False)

init_db()

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

if st.session_state['logged_in_user'] is None:
    st.title("🌟 Санаторий «Олтин Сой»")
    
    if not st.session_state['show_registration']:
        st.info("### 📱 Вход в систему")
        with st.form("login_form"):
            phone_input = st.text_input("Введите ваш номер телефона (или оставьте пустым для входа как Гость)").strip()
            admin_password = st.text_input("🔑 Пароль (только для Администратора)", type="password")
            sms_confirm = st.checkbox("Подтвердить по SMS / Согласен с условиями", value=True)
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
        st.info("### 📝 Регистрация")
        with st.form("reg_form"):
            p_phone = st.text_input("Номер телефона (Не обязательно)", value=st.session_state['reg_phone'])
            new_name = st.text_input("Имя, Фамилия")
            new_birth = st.text_input("Год рождения")
            new_id_type = st.selectbox("Документ", ["Паспорт", "Водительские права"])
            new_passport = st.text_input("Серия и номер документа")
            new_complaint = st.text_area("Жалобы")
            if st.form_submit_button("Создать аккаунт"):
                if not new_name:
                    st.error("Укажите Имя и Фамилию!")
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
                        send_telegram_notification(f"🔔 *Новый клиент:* {new_name} ({p_phone if p_phone else 'Без телефона'})")
                        st.rerun()
else:
    current_user = st.session_state['logged_in_user']
    role = current_user['role']
    
    st.sidebar.title("📱 Аккаунт")
    st.sidebar.write(f"ФИО: **{current_user['name']}**")
    st.sidebar.write(f"Тел: `{current_user['phone']}`")
    if st.sidebar.button("🚪 Выйти"):
        st.session_state['logged_in_user'] = None
        if token in global_sessions: del global_sessions[token]
        st.rerun()

    if role == 'Admin':
        st.title("💼 Панель Рустама")
        t1, t2, t3, t4, t5, t6 = st.tabs(["📊 Обзор", "👥 Управление Пациентами", "🏨 Палаты", "📅 Процедуры", "📤 Выписка/Семья", "📅 Отчеты"])

        with t1:
            st.subheader("Текущее состояние")
            p_df = run_query("SELECT * FROM users WHERE role='Пациент' AND room != '-'")
            st.dataframe(p_df, use_container_width=True)

        with t2:
            st.subheader("Регистрация + Мгновенное Бронирование")
            available_rooms = run_query("SELECT room_number, price_type, price_per_day FROM rooms WHERE status='Свободно'")
            room_options = [f"{row['room_number']} ({row['price_type']} - {row['price_per_day']} сум)" for _, row in available_rooms.iterrows()] if not available_rooms.empty else []
            
            with st.form("admin_full_reg_form"):
                adm_name = st.text_input("ФИО Пациента *")
                adm_phone = st.text_input("Телефон (Можно оставить пустым)")
                adm_birth = st.text_input("Год рождения")
                adm_passport = st.text_input("Серия/Номер паспорта")
                
                st.markdown("##### 🏨 Настройки проживания и заселения:")
                need_booking = st.checkbox("Заселить в палату прямо сейчас?", value=True)
                adm_room = st.selectbox("Выбрать свободную палату", room_options if room_options else ["Нет свободных палат"])
                adm_in_date = st.date_input("Дата заезда", value=datetime.now().date())
                adm_out_date = st.date_input("Дата выезда (До какого числа)", value=datetime.now().date() + timedelta(days=7))
                adm_guests = st.number_input("Количество человек (Семья)", min_value=1, max_value=10, value=1)
                
                adm_durations_str = st.text_input("Дни проживания каждого члена семьи (через запятую, например: 7, 7, 5). Оставьте пустым для расчета по датам выше.")
                
                adm_pay = st.selectbox("Оплата", ["Полностью", "Частично"])
                
                if st.form_submit_button("Зарегистрировать и заселить"):
                    if not adm_name:
                        st.error("ФИО обязательно для заполнения!")
                    else:
                        final_adm_phone = adm_phone.strip() if adm_phone.strip() else f"NoPhone_{str(uuid.uuid4())[:8]}"
                        
                        room_field = '-'
                        in_date_str = '-'
                        out_date_str = '-'
                        days = 0
                        cost = 0
                        durations_db_str = ''
                        
                        if need_booking and room_options and adm_room != "Нет свободных палат":
                            r_num = adm_room.split(" (")[0]
                            r_type = adm_room.split(" (")[1].split(" - ")[0]
                            
                            base_days = (adm_out_date - adm_in_date).days
                            if base_days <= 0: base_days = 1
                            
                            room_info = run_query("SELECT price_per_day FROM rooms WHERE room_number = ? AND price_type = ?", (r_num, r_type))
                            price = clean_numeric(room_info['price_per_day'][0]) if not room_info.empty else 0
                            
                            parsed_durations = []
                            if adm_durations_str.strip():
                                try:
                                    parsed_durations = [int(x.strip()) for x in adm_durations_str.split(",") if x.strip().isdigit()]
                                except:
                                    parsed_durations = []
                            
                            if len(parsed_durations) != int(adm_guests):
                                if len(parsed_durations) == 1:
                                    parsed_durations = parsed_durations * int(adm_guests)
                                else:
                                    parsed_durations = [base_days] * int(adm_guests)
                            
                            days = max(parsed_durations)
                            cost = sum(price * d for d in parsed_durations)
                            durations_db_str = ",".join(map(str, parsed_durations))
                            
                            adm_out_date = adm_in_date + timedelta(days=days)
                            
                            room_field = f"{r_num} ({r_type})"
                            in_date_str = str(adm_in_date)
                            out_date_str = str(adm_out_date)
                            
                            run_query("UPDATE rooms SET status = 'Занято' WHERE room_number = ? AND price_type = ?", (r_num, r_type), is_select=False)
                        
                        run_query('''
                            INSERT INTO users (name, phone, role, room, check_in_date, check_out_date, duration_days, guests_count, total_cost, birth_year, passport_series, payment_method, guest_durations)
                            VALUES (?, ?, 'Пациент', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (adm_name, final_adm_phone, room_field, in_date_str, out_date_str, days, int(adm_guests), cost, adm_birth, adm_passport, adm_pay, durations_db_str), is_select=False)
                        
                        msg = f"🏨 *Рустам зарегистрировал:* {adm_name}\n🛏 Палата: {room_field}\n👥 Гостей: {adm_guests}\n📅 Распределение дней: {durations_db_str if durations_db_str else days}\n💰 Сумма: {cost:,} сум"
                        send_telegram_notification(msg)
                        st.success("Пациент успешно сохранен!")
                        st.rerun()

        with t4:
            st.subheader("Назначение процедур")
            patients = run_query("SELECT phone, name FROM users WHERE role='Пациент'")
            p_opts = [f"{r['name']} ({r['phone']})" for _, r in patients.iterrows()] if not patients.empty else ["Нет пациентов"]
            with st.form("proc_form"):
                sel_p = st.selectbox("Пациент", p_opts)
                proc = st.selectbox("Процедура", ["Массаж", "Грязевые ванны", "Физиотерапия"])
                dt = st.text_input("Время", "Сегодня, 14:00")
                if st.form_submit_button("Назначить"):
                    if sel_p != "Нет пациентов":
                        ph = sel_p.split("(")[-1].replace(")", "")
                        run_query("INSERT INTO appointments (patient_phone, doctor_name, procedure_name, date_time) VALUES (?, 'Сапартошев А.', ?, ?)", (ph, proc, dt), is_select=False)
                        st.success("Успешно!")

        with t5:
            st.subheader("📤 Выписка (Полная или Частичный уезд семьи)")
            active_p = run_query("SELECT * FROM users WHERE role='Пациент' AND room != '-'")
            if not active_p.empty:
                p_choose = st.selectbox("Выберите семью/пациента для выписки", [f"{r['name']} ({r['phone']}) - {r['room']} [Гостей: {r['guests_count']}]" for _, r in active_p.iterrows()])
                chosen_phone = p_choose.split("(")[1].split(")")[0]
                p_data = run_query("SELECT * FROM users WHERE phone = ?", (chosen_phone,)).iloc[0]
                
                g_count = clean_numeric(p_data['guests_count'])
                
                if 'guest_durations' in p_data and p_data['guest_durations']:
                    st.info(f"📋 Планируемые дни проживания гостей при бронировании: **{p_data['guest_durations']}**")
                
                checkout_type = st.radio("Тип выписки:", ["Выписать ВСЮ семью полностью", f"Частичный выезд (Уезжает только часть людей из {g_count})"])
                
                if checkout_type == "Выписать ВСЮ семью полностью":
                    if st.button("🚪 Выписать полностью"):
                        run_query('''
                            INSERT INTO checkout_archive (name, phone, room, check_in_date, check_out_date, duration_days, guests_count, total_cost, payment_method, archive_date, comment)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Полный выезд')
                        ''', (p_data['name'], p_data['phone'], p_data['room'], p_data['check_in_date'], p_data['check_out_date'], str(p_data['duration_days']), str(g_count), str(p_data['total_cost']), p_data['payment_method'], str(datetime.now().date())), is_select=False)
                        
                        try:
                            r_num = p_data['room'].split(" (")[0]
                            r_type = p_data['room'].split(" (")[1].replace(")", "")
                            run_query("UPDATE rooms SET status = 'Свободно' WHERE room_number = ? AND price_type = ?", (r_num, r_type), is_select=False)
                        except: pass
                        
                        run_query("UPDATE users SET room='-', check_in_date='-', check_out_date='-', duration_days=0, total_cost=0, guests_count=1, guest_durations='' WHERE phone=?", (chosen_phone,), is_select=False)
                        st.success("Вся семья успешно выписана!")
                        st.rerun()
                else:
                    leaving_guests = st.number_input("Сколько человек уезжает раньше времени?", min_value=1, max_value=int(g_count)-1, value=1)
                    days_stayed = st.number_input("Сколько дней они фактически прожили до уезда?", min_value=1, max_value=30, value=3)
                    
                    if st.button("🚪 Оформить частичный уезд"):
                        try:
                            r_num = p_data['room'].split(" (")[0]
                            r_type = p_data['room'].split(" (")[1].replace(")", "")
                            room_info = run_query("SELECT price_per_day FROM rooms WHERE room_number = ? AND price_type = ?", (r_num, r_type))
                            price = clean_numeric(room_info['price_per_day'][0]) if not room_info.empty else 0
                        except: price = 0
                        
                        leaving_cost = price * int(days_stayed) * int(leaving_guests)
                        
                        run_query('''
                            INSERT INTO checkout_archive (name, phone, room, check_in_date, check_out_date, duration_days, guests_count, total_cost, payment_method, archive_date, comment)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (f"{p_data['name']} (Часть семьи)", p_data['phone'], p_data['room'], p_data['check_in_date'], str(datetime.now().date()), str(days_stayed), str(leaving_guests), str(leaving_cost), p_data['payment_method'], str(datetime.now().date()), f"Уехали раньше на {days_stayed} дн.") , is_select=False)
                        
                        new_guests_count = g_count - leaving_guests
                        orig_days = clean_numeric(p_data['duration_days'])
                        new_total_cost = (price * orig_days * new_guests_count) + leaving_cost
                        
                        run_query("UPDATE users SET guests_count = ?, total_cost = ? WHERE phone = ?", (int(new_guests_count), int(new_total_cost), chosen_phone), is_select=False)
                        st.success(f"Частичный выезд {leaving_guests} чел. оформлен. В палате осталось: {new_guests_count} чел.")
                        st.rerun()
            else:
                st.info("Нет активных пациентов.")

        with t6:
            st.subheader("Отчеты")
            arch = run_query("SELECT * FROM checkout_archive")
            st.dataframe(arch, use_container_width=True)

    elif role == 'Пациент':
        st.title(f"👤 Кабинет: {current_user['name']}")
        p_tab1, p_tab2 = st.tabs(["🏨 Бронирование", "📅 Мои Процедуры"])
        
        with p_tab1:
            if current_user['room'] == '-':
                av_rooms = run_query("SELECT room_number, price_type, price_per_day FROM rooms WHERE status='Свободно'")
                if not av_rooms.empty:
                    st.dataframe(av_rooms, use_container_width=True)
                    with st.form("client_book"):
                        r_sel = st.selectbox("Палата", [f"{r['room_number']} ({r['price_type']} - {r['price_per_day']} сум)" for _, r in av_rooms.iterrows()])
                        in_d = st.date_input("Дата заезда")
                        out_d = st.date_input("До какого числа (Дата выезда)", value=datetime.now().date() + timedelta(days=7))
                        gst = st.number_input("Количество человек", min_value=1, max_value=10, value=1)
                        client_durations_str = st.text_input("Дни проживания каждого члена семьи (через запятую, например: 7, 7, 5). Оставьте пустым для одинакового срока.")
                        
                        if st.form_submit_button("Забронировать"):
                            r_num = r_sel.split(" (")[0]
                            r_type = r_sel.split(" (")[1].split(" - ")[0]
                            base_days = (out_d - in_d).days
                            if base_days <= 0: base_days = 1
                            
                            room_info = run_query("SELECT price_per_day FROM rooms WHERE room_number = ? AND price_type = ?", (r_num, r_type))
                            price = clean_numeric(room_info['price_per_day'][0]) if not room_info.empty else 0
                            
                            parsed_durations = []
                            if client_durations_str.strip():
                                try:
                                    parsed_durations = [int(x.strip()) for x in client_durations_str.split(",") if x.strip().isdigit()]
                                except:
                                    parsed_durations = []
                            
                            if len(parsed_durations) != int(gst):
                                if len(parsed_durations) == 1:
                                    parsed_durations = parsed_durations * int(gst)
                                else:
                                    parsed_durations = [base_days] * int(gst)
                            
                            days = max(parsed_durations)
                            cost = sum(price * d for d in parsed_durations)
                            durations_db_str = ",".join(map(str, parsed_durations))
                            out_d = in_d + timedelta(days=days)
                            
                            run_query('''
                                UPDATE users SET room=?, check_in_date=?, check_out_date=?, duration_days=?, guests_count=?, total_cost=?, guest_durations=? WHERE phone=?
                            ''', (f"{r_num} ({r_type})", str(in_d), str(out_d), days, int(gst), cost, durations_db_str, current_user['phone']), is_select=False)
                            run_query("UPDATE rooms SET status='Занято' WHERE room_number=? AND price_type=?", (r_num, r_type), is_select=False)
                            
                            client_msg = f"🏨 *Бронь от клиента:* {current_user['name']}\nПалата: {r_num}\nРаспределение: {durations_db_str if durations_db_str else days} дн.\nДо: {out_d}"
                            send_telegram_notification(client_msg)
                            st.success("Успешно забронировано!")
                            st.rerun()
            else:
                st.info(f"Ваша палата: {current_user['room']}. До: {current_user['check_out_date']}")
