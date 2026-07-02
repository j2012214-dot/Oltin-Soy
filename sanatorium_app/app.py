import streamlit as st
import sqlite3
import pandas as pd
import qrcode
from io import BytesIO
from datetime import datetime, timedelta

# Настройка страницы клиники
st.set_page_config(page_title="Санаторий Олтин Сой", layout="wide")

# Полностью безопасная функция для работы с базой данных
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
        if "duplicate column name" in error_msg or "already exists" in error_msg:
            return True
        if is_select:
            return pd.DataFrame()
        return False
    finally:
        conn.close()

# Очистка аномальных строк с запятыми
def clean_numeric(val):
    if val is None:
        return 0
    s = str(val).strip()
    if ',' in s and (s.count(',') > 1 or '.' in s):
        s = s.split(',')[0]
    s = ''.join(c for c in s if c.isdigit() or c == '.')
    try:
        return int(float(s)) if s else 0
    except:
        return 0

# Инициализация структуры базы данных
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
            duration_days INTEGER,
            guests_count INTEGER,
            total_cost INTEGER,
            payment_method TEXT,
            archive_date TEXT
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

    columns_to_add = {
        "guests_count": "INTEGER DEFAULT 1",
        "birth_year": "TEXT DEFAULT '-'",
        "passport_series": "TEXT DEFAULT '-'",
        "id_type": "TEXT DEFAULT 'Паспорт'",
        "payment_method": "TEXT DEFAULT '-'"
    }
    for col, definition in columns_to_add.items():
        run_query(f"ALTER TABLE users ADD COLUMN {col} {definition}", is_select=False)

    run_query("INSERT OR IGNORE INTO users (name, phone, role) VALUES ('Рустам (Администратор)', '+998973208668', 'Admin')", is_select=False)
    run_query("UPDATE users SET name = 'Рустам (Администратор)' WHERE phone = '+998973208668'", is_select=False)

    rooms_count_df = run_query("SELECT COUNT(*) as count FROM rooms")
    rooms_count = rooms_count_df['count'][0] if (rooms_count_df is not None and not rooms_count_df.empty and 'count' in rooms_count_df.columns) else 0
    
    if rooms_count == 0:
        rooms_data = []
        for i in range(1, 14):
            rooms_data.append((f"0{i}" if i < 10 else f"{i}", "Корпус 1", "1", "Свободно", "Стандарт", 170000))
        for i in range(5):
            rooms_data.append((f"0{i}", "Корпус 1", "2", "Свободно", "Полу-Люкс", 200000))
        for i in range(1, 9):
            rooms_data.append((f"0{i}", "Корпус 2", "3", "Свободно", "Люкс", 250000))
            
        for r_num, corp, flr, stat, p_type, p_day in rooms_data:
            run_query("INSERT INTO rooms (room_number, corpus, floor, status, price_type, price_per_day) VALUES (?, ?, ?, ?, ?, ?)", (r_num, corp, flr, stat, p_type, p_day), is_select=False)

init_db()

# Сессии
@st.cache_resource(ttl=86400)
def get_global_sessions():
    return {}

global_sessions = get_global_sessions()

if 'session_token' not in st.session_state:
    import uuid
    st.session_state['session_token'] = str(uuid.uuid4())

token = st.session_state['session_token']

if 'logged_in_user' not in st.session_state:
    if token in global_sessions:
        st.session_state['logged_in_user'] = global_sessions[token]
    else:
        st.session_state['logged_in_user'] = None

if st.session_state['logged_in_user'] is not None:
    saved_phone = st.session_state['logged_in_user']['phone']
    user_refresh = run_query("SELECT * FROM users WHERE phone = ?", (saved_phone,))
    if user_refresh is not None and not user_refresh.empty:
        st.session_state['logged_in_user'] = user_refresh.iloc[0]
        global_sessions[token] = user_refresh.iloc[0]
    else:
        st.session_state['logged_in_user'] = None
        if token in global_sessions:
            del global_sessions[token]

if 'show_registration' not in st.session_state:
    st.session_state['show_registration'] = False
if 'reg_phone' not in st.session_state:
    st.session_state['reg_phone'] = ""

# ---------------------------------------------------------
# СТАРТОВАЯ СТРАНИЦА
# ---------------------------------------------------------
if st.session_state['logged_in_user'] is None:
    st.title("🌟 Добро пожаловать в Санаторий «Олтин Сой»")
    st.subheader("Система онлайн-бронирования и управления услугами")
    st.write("Пожалуйста, зарегистрируйтесь или войдите, используя ваш номер телефона.")
    
    if not st.session_state['show_registration']:
        st.info("### 📱 Вход в систему")
        with st.form("mobile_login_form"):
            phone_input = st.text_input("Введите ваш номер телефона (например, +998973208668)", value="", key="login_phone").strip()
            admin_password = st.text_input("🔑 Если вы Администратор, введите пароль", type="password", key="admin_pin")
            sms_confirm = st.checkbox("Подтвердить код из SMS", key="login_sms")
            submit_login = st.form_submit_button("🚀 Войти в систему")
            
        if submit_login:
            if not phone_input:
                st.error("Пожалуйста, введите ваш номер телефона.")
            elif not sms_confirm:
                st.error("Пожалуйста, отметьте галочку 'Подтвердить код из SMS'.")
            else:
                password_correct = True
                if phone_input == "+998973208668":
                    if admin_password != "XojiOna62":
                        password_correct = False
                        st.error("Неверный пароль администратора!")
                
                if password_correct:
                    user_df = run_query("SELECT * FROM users WHERE phone = ?", (phone_input,))
                    if user_df is not None and not user_df.empty:
                        st.session_state['logged_in_user'] = user_df.iloc[0]
                        global_sessions[token] = user_df.iloc[0]
                        st.success("Вы успешно вошли в систему!")
                        st.rerun()
                    else:
                        st.session_state['show_registration'] = True
                        st.session_state['reg_phone'] = phone_input
                        st.rerun()
                        
        if st.button("📝 Я новый клиент (Регистрация)"):
            st.session_state['show_registration'] = True
            st.rerun()

    else:
        st.info("### 📝 Регистрация нового пациента")
        with st.form("main_reg_form_isolated"):
            p_phone = st.text_input("Номер Пациента (Телефон)", value=st.session_state['reg_phone'], key="reg_phone_field")
            new_name = st.text_input("Имя, Фамилия", key="reg_name_field")
            new_birth = st.text_input("Год рождения", key="reg_birth_field")
            new_id_type = st.selectbox("Тип удостоверение", ["Паспорт", "Водительские права"], key="reg_id_type_field")
            new_passport = st.text_input("Паспорт серия/номер", key="reg_passport_field")
            new_complaint = st.text_area("Ваши жалобы при поступлении", key="reg_complaint_field")
            reg_sms = st.checkbox("Подтверждаю код из SMS для регистрации", key="reg_sms_field")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                submit_reg = st.form_submit_button("✨ Создать аккаунт и войти")
            with col_b2:
                cancel_reg = st.form_submit_button("⬅️ Вернуться назад к входу")

        if cancel_reg:
            st.session_state['show_registration'] = False
            st.session_state['reg_phone'] = ""
            st.rerun()

        if submit_reg:
            if not p_phone:
                st.error("Пожалуйста, укажите Номер Пациента!")
            elif not new_name:
                st.error("Пожалуйста, введите ваше Имя и Фамилию!")
            elif not new_birth:
                st.error("Пожалуйста, укажите Год рождения!")
            elif not new_passport:
                st.error("Пожалуйста, укажите Серию/Номер документа!")
            elif not reg_sms:
                st.error("Пожалуйста, подтвердите регистрацию галочкой SMS!")
            else:
                check_user = run_query("SELECT * FROM users WHERE phone = ?", (p_phone,))
                if check_user is not None and not check_user.empty:
                    st.error("Пользователь с таким номером телефона уже зарегистрирован!")
                else:
                    run_query('''
                        INSERT INTO users (name, phone, role, complaints, birth_year, passport_series, id_type) 
                        VALUES (?, ?, 'Пациент', ?, ?, ?, ?)
                    ''', (new_name, p_phone, new_complaint, new_birth, new_passport, new_id_type), is_select=False)
                    
                    user_res = run_query("SELECT * FROM users WHERE phone = ?", (p_phone,))
                    if user_res is not None and not user_res.empty:
                        fresh_user = user_res.iloc[0]
                        st.session_state['show_registration'] = False
                        st.session_state['reg_phone'] = ""
                        st.session_state['logged_in_user'] = fresh_user
                        global_sessions[token] = fresh_user
                        st.success("Вы успешно зарегистрированы!")
                        st.rerun()

# ---------------------------------------------------------
# ЛИЧНЫЙ КАБИНЕТ
# ---------------------------------------------------------
else:
    current_user = st.session_state['logged_in_user']
    role = current_user['role']
    
    st.sidebar.title("📱 Ваш аккаунт")
    st.sidebar.write(f"Вы вошли как: **{current_user['name']}**")
    st.sidebar.write(f"Номер: `{current_user['phone']}`")
    st.sidebar.write(f"Роль: `{role}`")
    
    if st.sidebar.button("🚪 Выйти из системы", use_container_width=True):
        st.session_state['logged_in_user'] = None
        if token in global_sessions:
            del global_sessions[token]
        st.rerun()

    if role == 'Admin':
        st.title("💼 Панель администратора: Рустам")
        t1, t2, t3, t4, t5, t6 = st.tabs(["📊 Обзор", "👥 Управление Пациентами", "🏨 Палаты", "📅 Назначение процедур", "📤 Выписка", "📅 Отчеты за год"])

        with t1:
            st.subheader("Мониторинг санатория")
            col1, col2, col3 = st.columns(3)
            p_df = run_query("SELECT COUNT(*) as c FROM users WHERE role='Пациент' AND room != '-'")
            r_df = run_query("SELECT COUNT(*) as c FROM rooms WHERE status='Занято'")
            a_df = run_query("SELECT COUNT(*) as c FROM appointments")
            total_p = p_df['c'][0] if (p_df is not None and not p_df.empty and 'c' in p_df.columns) else 0
            total_r = r_df['c'][0] if (r_df is not None and not r_df.empty and 'c' in r_df.columns) else 0
            total_a = a_df['c'][0] if (a_df is not None and not a_df.empty and 'c' in a_df.columns) else 0
            col1.metric("Активные пациенты", total_p)
            col2.metric("Занято палат", total_r)
            col3.metric("Активных процедур", total_a)
            
            all_patients = run_query('''
                SELECT name as 'Имя, Фамилия', phone as 'Номер Пациента', birth_year as 'Год рождения',
                       id_type as 'Документ', passport_series as 'Серия/Номер', room as 'Палата', 
                       check_in_date as 'Дата заезда', duration_days as 'Дней', total_cost as 'Итого (сум)',
                       payment_method as 'Способ оплаты'
                FROM users WHERE role='Пациент' AND room != '-'
            ''')
            if all_patients is not None and not all_patients.empty:
                st.dataframe(all_patients, use_container_width=True)

        with t2:
            st.subheader("Регистрация нового пациента администратором")
            with st.form("admin_reg_form"):
                p_name = st.text_input("Имя, Фамилия пациента")
                p_phone = st.text_input("Номер Пациента (Телефон)")
                p_birth = st.text_input("Год рождения")
                p_id_type = st.selectbox("Тип удостоверение", ["Паспорт", "Водительские права"])
                p_passport = st.text_input("Паспорт серия/номер")
                p_package = st.selectbox("Пакет услуг", ["Стандарт", "Полу-Люкс", "Люкс"])
                p_complaints = st.text_area("Жалобы")
                if st.form_submit_button("Зарегистрировать пациента"):
                    if p_name and p_phone and p_birth and p_passport:
                        run_query('''
                            INSERT INTO users (name, phone, role, package, complaints, birth_year, passport_series, id_type) 
                            VALUES (?, ?, 'Пациент', ?, ?, ?, ?, ?)
                        ''', (p_name, p_phone, p_package, p_complaints, p_birth, p_passport, p_id_type), is_select=False)
                        st.success("Пациент успешно добавлен в систему!")
                        st.rerun()
            
            st.markdown("---")
            st.subheader("🗑️ Удаление аккаунтов клиентов (пробных или ошибочных)")
            all_db_patients = run_query("SELECT phone, name, room FROM users WHERE role='Пациент'")
            
            if all_db_patients is not None and not all_db_patients.empty:
                patient_to_delete_str = st.selectbox(
                    "Выберите пациента для полного удаления из базы данных", 
                    [f"{row['name']} ({row['phone']}) — Палата: {row['room']}" for _, row in all_db_patients.iterrows()],
                    key="delete_patient_select"
                )
                
                if st.button("❌ Удалить выбранного клиента навсегда", use_container_width=True, type="primary"):
                    selected_del_phone = patient_to_delete_str.split("(")[1].split(")")[0]
                    
                    p_info_df = run_query("SELECT room FROM users WHERE phone = ?", (selected_del_phone,))
                    if p_info_df is not None and not p_info_df.empty:
                        p_room = p_info_df['room'][0]
                        if p_room != '-':
                            try:
                                r_num = p_room.split(" (")[0]
                                r_type = p_room.split(" (")[1].replace(")", "")
                                run_query("UPDATE rooms SET status = 'Свободно' WHERE room_number = ? AND price_type = ?", (r_num, r_type), is_select=False)
                            except:
                                pass
                    
                    run_query("DELETE FROM users WHERE phone = ?", (selected_del_phone,), is_select=False)
                    run_query("DELETE FROM appointments WHERE patient_phone = ?", (selected_del_phone,), is_select=False)
                    st.success(f"Аккаунт пациента с номером {selected_del_phone} полностью удален.")
                    st.rerun()
            else:
                st.info("В базе данных пока нет зарегистрированных пациентов.")

        with t3:
            st.subheader("Состояние номерного фонда и цены")
            rooms_df = run_query("SELECT room_number as 'Номер комнаты', price_type as 'Тип палаты', price_per_day as 'Цена за 1 чел/день (сум)', corpus as 'Корпус', floor as 'Этаж', status as 'Статус' FROM rooms")
            if rooms_df is not None and not rooms_df.empty:
                st.dataframe(rooms_df, use_container_width=True)

        with t4:
            st.subheader("Назначить процедуру")
            patients_list = run_query("SELECT phone, name FROM users WHERE role='Пациент'")
            
            with st.form("appointment_form_fixed"):
                options = [f"{row['name']} ({row['phone']})" for _, row in patients_list.iterrows()] if (patients_list is not None and not patients_list.empty and 'name' in patients_list.columns) else ["Нет пациентов"]
                chosen_patient = st.selectbox("Пациент", options)
                chosen_doctor = st.selectbox("Врач", ["Сапартошев Абдураззок"])
                proc_name = st.selectbox("Процедура", ["Общий осмотр", "Массаж", "Физиотерапия", "Грязевые ванны"])
                date_time_str = st.text_input("Дата и время", value="Сегодня, 12:00")
                submit_btn = st.form_submit_button("Назначить процедуру")
                
                if submit_btn:
                    if chosen_patient != "Нет пациентов":
                        p_phone_extracted = chosen_patient.split("(")[-1].replace(")", "")
                        run_query("INSERT INTO appointments (patient_phone, doctor_name, procedure_name, date_time) VALUES (?, ?, ?, ?)", (p_phone_extracted, chosen_doctor, proc_name, date_time_str), is_select=False)
                        st.success("Процедура успешно назначена!")
                    else:
                        st.error("Невозможно назначить процедуру: список пациентов пуст.")

        with t5:
            st.subheader("📤 Выписка пациентов и архивация")
            active_p = run_query("SELECT name, phone, room, check_in_date, duration_days, guests_count, total_cost, payment_method FROM users WHERE role='Пациент' AND room != '-'")
            if active_p is not None and not active_p.empty:
                patient_to_checkout = st.selectbox(
                    "Выберите активного пациента для оформления выписки", 
                    [f"{row['name']} ({row['phone']}) - Палата {row['room']}" for _, row in active_p.iterrows()]
                )
                if st.button("🚪 Оформить выписку и отправить в архив", use_container_width=True):
                    selected_phone = patient_to_checkout.split("(")[1].split(")")[0]
                    p_res = run_query("SELECT * FROM users WHERE phone = ?", (selected_phone,))
                    if p_res is not None and not p_res.empty:
                        p_data = p_res.iloc[0]
                        
                        pure_days = clean_numeric(p_data['duration_days'])
                        pure_guests = clean_numeric(p_data['guests_count'])
                        pure_cost = clean_numeric(p_data['total_cost'])
                        
                        run_query('''
                            INSERT INTO checkout_archive (name, phone, room, check_in_date, duration_days, guests_count, total_cost, payment_method, archive_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (p_data['name'], p_data['phone'], p_data['room'], p_data['check_in_date'], pure_days, pure_guests, pure_cost, p_data['payment_method'], str(datetime.now().date())), is_select=False)
                        
                        try:
                            r_num = p_data['room'].split(" (")[0]
                            r_type = p_data['room'].split(" (")[1].replace(")", "")
                            run_query("UPDATE rooms SET status = 'Свободно' WHERE room_number = ? AND price_type = ?", (r_num, r_type), is_select=False)
                        except:
                            pass
                        
                        run_query("UPDATE users SET room = '-', check_in_date = '-', duration_days = 0, total_cost = 0, payment_method = '-' WHERE phone = ?", (selected_phone,), is_select=False)
                        st.success("Пациент успешно выписан и автоматически перенесен в 'Отчеты за год'!")
                        st.rerun()
            else:
                st.info("Нет активных проживающих пациентов для выписки.")
                
            archive_df = run_query("SELECT name as 'Имя, Фамилия', phone as 'Номер', room as 'Палата', check_in_date as 'Заезд', duration_days as 'Дней', total_cost as 'Оплачено', payment_method as 'Тип оплаты', archive_date as 'Дата выписки' FROM checkout_archive")
            if archive_df is not None and not archive_df.empty:
                archive_df['Дней'] = archive_df['Дней'].apply(clean_numeric)
                archive_df['Оплачено'] = archive_df['Оплачено'].apply(clean_numeric)
                st.dataframe(archive_df, use_container_width=True)

        with t6:
            # ВКЛАДКА ОТЧЕТЫ ЗА ГОД С КНОПКОЙ КОРЗИНЫ
            st.subheader("📊 Отчеты за год")
            
            # Верхний блок управления для удаления в один клик
            archive_selector_df = run_query("SELECT id, name, total_cost, archive_date FROM checkout_archive")
            
            if archive_selector_df is not None and not archive_selector_df.empty:
                col_title, col_trash = st.columns([3, 1])
                with col_trash:
                    # Имитируем корзину выбора для удаления в один клик
                    selected_archive_row = st.selectbox(
                        "🗑️ Выберите запись для удаления из отчетов",
                        [f"{row['name']} ({row['total_cost']:,} сум) от {row['archive_date']} [ID:{row['id']}]" for _, row in archive_selector_df.iterrows()]
                    )
                    if st.button("🗑️ Удалить запись из отчетов", use_container_width=True, type="primary"):
                        extracted_id = selected_archive_row.split("[ID:")[-1].replace("]", "")
                        run_query("DELETE FROM checkout_archive WHERE id = ?", (extracted_id,), is_select=False)
                        st.success("Запись успешно стерта из годового архива отчетности!")
                        st.rerun()
            
            archive_data = run_query("SELECT total_cost FROM checkout_archive")
            total_revenue = 0
            if archive_data is not None and not archive_data.empty:
                total_revenue = sum(clean_numeric(x) for x in archive_data['total_cost'])
                
            st.metric("Общая годовая выручка от выписанных клиентов", f"{total_revenue:,} сум")
            
            full_archive = run_query("SELECT name as 'ФИО', room as 'Палата', duration_days as 'Дней', total_cost as 'Сумма', archive_date as 'Дата выписки' FROM checkout_archive")
            if full_archive is not None and not full_archive.empty:
                full_archive['Дней'] = full_archive['Дней'].apply(clean_numeric)
                full_archive['Сумма'] = full_archive['Сумма'].apply(clean_numeric)
                st.dataframe(full_archive, use_container_width=True)

    elif role == 'Пациент':
        st.title(f"👤 Кабинет Пациента: {current_user['name']}")
        p_tab1, p_tab2 = st.tabs(["🏨 Бронирование Палаты", "📅 Мои Процедуры"])
        
        with p_tab1:
            if current_user['room'] == '-':
                available_rooms = run_query("SELECT * FROM rooms WHERE status='Свободно'")
                
                if available_rooms is not None and not available_rooms.empty and 'room_number' in available_rooms.columns:
                    display_cols = [c for c in ['room_number', 'price_type', 'price_per_day', 'corpus'] if c in available_rooms.columns]
                    st.dataframe(available_rooms[display_cols], use_container_width=True)
                else:
                    st.info("В данный момент все палаты заняты или список пуст.")
                
                with st.form("book_room"):
                    room_options = []
                    if available_rooms is not None and not available_rooms.empty and 'room_number' in available_rooms.columns:
                        room_options = [f"{row['room_number']} ({row['price_type']} - {row['price_per_day']} сум)" for _, row in available_rooms.iterrows()]
                    
                    selected_room_idx = st.selectbox("Выберите номер палаты", room_options)
                    check_in_date = st.date_input("Выберите дату заезда", value=datetime.now().date())
                    duration = st.number_input("На сколько дней забронировать?", min_value=1, max_value=30, value=1)
                    guests = st.number_input("Сколько человек будет проживать?", min_value=1, max_value=10, value=1)
                    pay_method = st.selectbox("Способ оплаты", ["Частично", "Полностью"])
                    
                    if st.form_submit_button("Подтвердить бронирование"):
                        if selected_room_idx:
                            r_num = selected_room_idx.split(" (")[0]
                            r_type = selected_room_idx.split(" (")[1].split(" - ")[0]
                            room_info = run_query("SELECT price_per_day FROM rooms WHERE room_number = ? AND price_type = ?", (r_num, r_type))
                            if room_info is not None and not room_info.empty and 'price_per_day' in room_info.columns:
                                price_per_day = clean_numeric(room_info['price_per_day'][0])
                                total_cost = price_per_day * int(duration) * int(guests)
                                
                                run_query('''
                                    UPDATE users 
                                    SET room = ?, check_in_date = ?, duration_days = ?, guests_count = ?, total_cost = ?, payment_method = ? 
                                    WHERE phone = ?
                                ''', (f"{r_num} ({r_type})", str(check_in_date), int(duration), int(guests), int(total_cost), pay_method, current_user['phone']), is_select=False)
                                run_query("UPDATE rooms SET status = 'Занято' WHERE room_number = ? AND price_type = ?", (r_num, r_type), is_select=False)
                                st.success(f"🎉 Палата {r_num} забронирована!")
                                st.rerun()
            else:
                st.info(f"У вас уже оформлено активное бронирование палаты: **{current_user['room']}**.")

        with p_tab2:
            st.write("### Ваше расписание лечебных процедур")
            my_appointments = run_query("SELECT doctor_name as 'Врач', procedure_name as 'Процедура', date_time as 'Дата/Время', status as 'Статус' FROM appointments WHERE patient_phone = ?", (current_user['phone'],))
            if my_appointments is not None and not my_appointments.empty:
                st.dataframe(my_appointments, use_container_width=True)
