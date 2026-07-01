import streamlit as st
import sqlite3
import pandas as pd
import qrcode
from io import BytesIO

# Настройка страницы клиники
st.set_page_config(page_title="Санаторий Олтин Сой", layout="wide")

# Функция для работы с базой данных
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
        st.error(f"Ошибка БД: {e}")
        return None
    finally:
        conn.close()

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
            complaints TEXT DEFAULT '-'
        )
    ''', is_select=False)

    run_query('''
        CREATE TABLE IF NOT EXISTS rooms (
            room_number TEXT NOT NULL,
            corpus TEXT NOT NULL,
            floor TEXT NOT NULL,
            status TEXT DEFAULT 'Свободно',
            price TEXT DEFAULT '0',
            PRIMARY KEY (room_number, price)
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

    run_query('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT,
            rating INTEGER,
            comment TEXT
        )
    ''', is_select=False)

    # Стартовые данные (Обнуление счетчиков для каждого типа палат)
    rooms_count = run_query("SELECT COUNT(*) as count FROM rooms")['count'][0]
    if rooms_count == 0:
        run_query("INSERT OR IGNORE INTO users (name, phone, role) VALUES ('Махлиё (Администратор)', '+998970978668', 'Admin')", is_select=False)
        run_query("INSERT OR IGNORE INTO users (name, phone, role) VALUES ('Доктор Петров (Терапевт)', '+79992223344', 'Врач')", is_select=False)
        run_query("INSERT OR IGNORE INTO users (name, phone, role) VALUES ('Доктор Ахмедов (Физиотерапевт)', '+998901112233', 'Врач')", is_select=False)
        
        rooms_data = []
        
        # 1. Стандарт: счетчик с 00 до 13
        for i in range(14):
            rooms_data.append((f"0{i}" if i < 10 else f"{i}", "Корпус 1", "1", "Свободно", "Стандарт"))
            
        # 2. Полу-Люкс: счетчик с 00 до 04
        for i in range(5):
            rooms_data.append((f"0{i}", "Корпус 1", "2", "Свободно", "Полу-Люкс"))
            
        # 3. Люкс: счетчик с 01 до 08
        for i in range(1, 9):
            rooms_data.append((f"0{i}", "Корпус 2", "3", "Свободно", "Люкс"))
            
        for r_num, corp, flr, stat, prc in rooms_data:
            run_query("INSERT INTO rooms (room_number, corpus, floor, status, price) VALUES (?, ?, ?, ?, ?)", (r_num, corp, flr, stat, prc), is_select=False)

init_db()

# Использование сессии для авторизации
if 'logged_in_user' not in st.session_state:
    st.session_state['logged_in_user'] = None

# ---------------------------------------------------------
# ГЛАВНОЕ МЕНЮ И СТАРТОВАЯ СТРАНИЦА (ЕСЛИ НЕ АВТОРИЗОВАН)
# ---------------------------------------------------------
if st.session_state['logged_in_user'] is None:
    st.title("🌟 Добро пожаловать в Санаторий «Олтин Сой»")
    st.subheader("Система онлайн-бронирования и управления услугами")
    st.write("Пожалуйста, зарегистрируйтесь или войдите, используя ваш номер телефона, для доступа к услугам санатория.")
    
    # Поля авторизации и регистрации на главном экране
    st.info("### 📱 Вход в систему / Регистрация")
    phone_input = st.text_input("Введите ваш номер телефона", value="+998970978668").strip()
    sms_confirm = st.checkbox("Подтвердить код из SMS")
    
    if phone_input and sms_confirm:
        user_df = run_query("SELECT * FROM users WHERE phone = ?", (phone_input,))
        if not user_df.empty:
            st.session_state['logged_in_user'] = user_df.iloc[0]
            st.success("Вы успешно вошли в систему!")
            st.rerun()
        else:
            st.warning("Ваш номер не найден в базе данных. Пожалуйста, пройдите быструю регистрацию ниже:")
            with st.form("main_reg_form"):
                new_name = st.text_input("Ваше Имя и Фамилия")
                new_complaint = st.text_area("Ваши жалобы при поступлении")
                if st.form_submit_button("Зарегистрироваться и войти"):
                    if new_name:
                        run_query("INSERT INTO users (name, phone, role, complaints) VALUES (?, ?, 'Пациент', ?)", (new_name, phone_input, new_complaint), is_select=False)
                        fresh_user = run_query("SELECT * FROM users WHERE phone = ?", (phone_input,)).iloc[0]
                        st.session_state['logged_in_user'] = fresh_user
                        st.success("Регистрация завершена!")
                        st.rerun()
                    else:
                        st.error("Пожалуйста, введите ваше Имя и Фамилию.")

# ---------------------------------------------------------
# ЕСЛИ ПОЛЬЗОВАТЕЛЬ АВТОРИЗОВАН — ПОКАЗЫВАЕМ ЕГО ЛИЧНЫЙ КАБИНЕТ
# ---------------------------------------------------------
else:
    current_user = st.session_state['logged_in_user']
    role = current_user['role']
    
    # Сайдбар управления аккаунтом
    st.sidebar.title("📱 Ваш аккаунт")
    st.sidebar.write(f"Вы вошли как: **{current_user['name']}**")
    st.sidebar.write(f"Номер: `{current_user['phone']}`")
    st.sidebar.write(f"Роль: `{role}`")
    
    if st.sidebar.button("🚪 Выйти из системы", use_container_width=True):
        st.session_state['logged_in_user'] = None
        st.rerun()
        
    # Функция генерации QR-кода
    def render_qr(data_text):
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(data_text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf)
        st.sidebar.image(buf.getvalue(), caption="Персональный QR-код для ресепшена", width=150)
        
    render_qr(f"User: {current_user['name']} | Role: {role} | Phone: {current_user['phone']}")

    # 1. ПАНЕЛЬ АДМИНИСТРАТОРА (Махлиё)
    if role == 'Admin':
        st.title("💼 Панель администратора: Махлиё")
        t1, t2, t3, t4, t5 = st.tabs(["📊 Обзор", "👥 Пациенты", "🏨 Палаты", "📅 Назначение процедур", "💬 Отзывы"])

        with t1:
            st.subheader("Мониторинг санатория")
            col1, col2, col3 = st.columns(3)
            total_p = run_query("SELECT COUNT(*) as c FROM users WHERE role='Пациент'")['c'][0]
            total_r = run_query("SELECT COUNT(*) as c FROM rooms WHERE status='Занято'")['c'][0]
            total_a = run_query("SELECT COUNT(*) as c FROM appointments")['c'][0]
            col1.metric("Всего пациентов", total_p)
            col2.metric("Занято палат", total_r)
            col3.metric("Активных процедур", total_a)
            
            st.write("### Текущие пациенты")
            all_patients = run_query("SELECT name as 'Имя', phone as 'Телефон', room as 'Палата', package as 'Тариф' FROM users WHERE role='Пациент'")
            st.dataframe(all_patients, use_container_width=True)

        with t2:
            st.subheader("Регистрация нового пациента администратором")
            with st.form("admin_reg_form"):
                p_name = st.text_input("Имя Фамилия пациента")
                p_phone = st.text_input("Номер телефона")
                p_package = st.selectbox("Пакет услуг", ["Стандарт", "Полу-Люкс", "Люкс"])
                p_complaints = st.text_area("Жалобы")
                if st.form_submit_button("Зарегистрировать пациента"):
                    if p_name and p_phone:
                        run_query("INSERT INTO users (name, phone, role, package, complaints) VALUES (?, ?, 'Пациент', ?, ?)", (p_name, p_phone, p_package, p_complaints), is_select=False)
                        st.success("Пациент успешно добавлен в систему!")
                        st.rerun()

        with t3:
            st.subheader("Состояние номерного фонда")
            rooms_df = run_query("SELECT room_number as 'Номер комнаты', price as 'Тип палаты', corpus as 'Корпус', floor as 'Этаж', status as 'Статус' FROM rooms")
            st.dataframe(rooms_df, use_container_width=True)

        with t4:
            st.subheader("Назначить процедуру")
            patients_list = run_query("SELECT phone, name FROM users WHERE role='Пациент'")
            doctors_list = run_query("SELECT name FROM users WHERE role='Врач'")
            
            with st.form("appointment_form"):
                chosen_patient = st.selectbox("Пациент", [f"{row['name']} ({row['phone']})" for _, row in patients_list.iterrows()] if not patients_list.empty else ["Нет пациентов"])
                chosen_doctor = st.selectbox("Врач", doctors_list['name'].tolist() if not doctors_list.empty else ["Нет врачей"])
                proc_name = st.selectbox("Процедура", ["Общий осмотр", "Массаж", "Физиотерапия", "Грязевые ванны"])
                date_time_str = st.text_input("Дата и время", value="Сегодня, 12:00")
                if st.form_submit_button("Назначить процедуру"):
                    p_phone_extracted = chosen_patient.split("(")[-1].replace(")", "") if "(" in chosen_patient else ""
                    run_query("INSERT INTO appointments (patient_phone, doctor_name, procedure_name, date_time) VALUES (?, ?, ?, ?)", (p_phone_extracted, chosen_doctor, proc_name, date_time_str), is_select=False)
                    st.success("Процедура успешно назначена!")

        with t5:
            st.subheader("Отзывы")
            reviews_df = run_query("SELECT * FROM reviews")
            st.dataframe(reviews_df, use_container_width=True)

    # 2. КАБИНЕТ ПАЦИЕНТА
    elif role == 'Пациент':
        st.title(f"👤 Кабинет Пациента: {current_user['name']}")
        p_tab1, p_tab2 = st.tabs(["🏨 Бронирование Палаты", "📅 Мои Процедуры"])
        
        with p_tab1:
            available_rooms = run_query("SELECT * FROM rooms WHERE status='Свободно'")
            st.write("### Доступные для бронирования палаты")
            st.dataframe(available_rooms[['room_number', 'price', 'corpus', 'status']], use_container_width=True)
            with st.form("book_room"):
                selected_room_idx = st.selectbox("Выберите номер палаты", [f"{row['room_number']} ({row['price']})" for _, row in available_rooms.iterrows()] if not available_rooms.empty else [])
                if st.form_submit_button("Подтвердить бронирование"):
                    r_num = selected_room_idx.split(" (")[0]
                    r_type = selected_room_idx.split(" (")[1].replace(")", "")
                    run_query("UPDATE users SET room = ? WHERE phone = ?", (f"{r_num} ({r_type})", current_user['phone']), is_select=False)
                    run_query("UPDATE rooms SET status = 'Занято' WHERE room_number = ? AND price = ?", (r_num, r_type), is_select=False)
                    st.success(f"Палата {r_num} ({r_type}) успешно забронирована за вами!")
                    st.rerun()

        with p_tab2:
            st.write("### Ваше расписание лечебных процедур")
            my_appointments = run_query("SELECT doctor_name as 'Врач', procedure_name as 'Процедура', date_time as 'Дата/Время', status as 'Статус' FROM appointments WHERE patient_phone = ?", (current_user['phone'],))
            st.dataframe(my_appointments, use_container_width=True)

    # 3. КАБИНЕТ ВРАЧА
    elif role == 'Врач':
        st.title(f"🩺 Рабочее место Врача: {current_user['name']}")
        st.write("### Список назначенных к вам пациентов")
        doc_appointments = run_query("SELECT id as 'ID Назначения', patient_phone as 'Телефон пациента', procedure_name as 'Процедура', date_time as 'Дата/Время', status as 'Статус' FROM appointments WHERE doctor_name = ?", (current_user['name'],))
        st.dataframe(doc_appointments, use_container_width=True)
