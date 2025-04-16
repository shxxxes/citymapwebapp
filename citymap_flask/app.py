import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from urllib.parse import urlparse
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'secret_key'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Функция для проверки расширений файлов
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db_url = "mysql://root:cytxyYnjPyYDjsfkyKLEhPHsNyxumpkT@metro.proxy.rlwy.net:10106/railway"
parsed_url = urlparse(db_url)

DB_CONFIG = {
    'host': parsed_url.hostname,
    'user': parsed_url.username,
    'password': parsed_url.password,
    'database': parsed_url.path[1:],
    'port': parsed_url.port
}


@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    sort_by = request.args.get('sort_by', 'newest')

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    if sort_by == 'oldest':
        cursor.execute("SELECT * FROM locations ORDER BY created_at ASC")
    else:
        cursor.execute("SELECT * FROM locations ORDER BY created_at DESC")

    locations = cursor.fetchall()
    conn.close()

    return render_template('index.html', locations=locations, username=session['username'])


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['name']
        password = request.form['password']

        # Соединение с базой данных
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Проверка существования пользователя с указанным именем
        cursor.execute("SELECT * FROM users WHERE name = %s", (username,))
        user = cursor.fetchone()

        if user and user['password'] == password:  # Простое сравнение пароля
            session['username'] = username
            return redirect(url_for('index'))  # Перенаправление на главную страницу
        else:
            flash('Неверное имя пользователя или пароль', 'danger')

        conn.close()

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name, password) VALUES (%s, %s)", (name, password))
        conn.commit()
        conn.close()

        flash("Регистрация прошла успешно", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/add_location', methods=['GET', 'POST'])
def add_location():
    if request.method == 'POST':
        name = request.form['name']
        type_ = request.form['type']
        description = request.form['description']
        address = request.form['address']

        # Сохранение локации в базу данных
        try:
            connection = mysql.connector.connect(**DB_CONFIG)
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO locations (name, type, description, address)
                VALUES (%s, %s, %s, %s)
            """, (name, type_, description, address))
            connection.commit()
            connection.close()
            flash('Локация успешно добавлена!', 'success')
            return redirect(url_for('index'))
        except mysql.connector.Error as err:
            flash(f"Ошибка: {err}", 'danger')

    # Получаем все категории из базы данных
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()
    cursor.execute("SELECT id, name FROM categories")  # Получаем id и имя категории
    categories = cursor.fetchall()
    connection.close()

    return render_template('add_location.html', categories=categories)

@app.route('/location/<int:location_id>', methods=['GET', 'POST'])
def location_info(location_id):
    if request.method == 'POST':
        # Получаем данные отзыва
        rating = request.form['rating']
        review_text = request.form['review_text']
        user_name = session.get('username')

        try:
            connection = mysql.connector.connect(**DB_CONFIG)
            cursor = connection.cursor(dictionary=True)

            # Получение ID пользователя по имени
            cursor.execute("SELECT id FROM users WHERE name = %s", (user_name,))
            user_row = cursor.fetchone()

            if user_row is None:
                flash("Пользователь не найден.", "danger")
                return redirect(url_for('location_info', location_id=location_id))

            user_id = user_row['id']

            # Сохраняем отзыв
            cursor.execute("""
                INSERT INTO reviews (location_id, user_id, rating, review_text)
                VALUES (%s, %s, %s, %s)
            """, (location_id, user_id, rating, review_text))
            connection.commit()
            connection.close()

            flash('Отзыв успешно добавлен!', 'success')
            return redirect(url_for('location_info', location_id=location_id))
        except mysql.connector.Error as err:
            flash(f"Ошибка при добавлении отзыва: {err}", 'danger')

    # Получение информации о локации
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM locations WHERE id = %s", (location_id,))
    location = cursor.fetchone()

    cursor.execute("SELECT name FROM categories WHERE id = %s", (location['type'],))
    category_row = cursor.fetchone()
    location_type = category_row['name'] if category_row else 'Неизвестно'

    # Получение отзывов с именами пользователей
    cursor.execute("""
        SELECT r.rating, r.review_text, u.name AS user_name
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.location_id = %s
    """, (location_id,))
    reviews = cursor.fetchall()

    connection.close()

    return render_template(
        'location_info.html',
        location=location,
        location_type=location_type,
        reviews=reviews,
        username=session.get('username')
    )

@app.route('/add_review/<int:location_id>', methods=['POST'])
def add_review(location_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    # Получаем данные отзыва
    rating = request.form['rating']
    review_text = request.form['review_text']
    username = session['username']

    # Сохраняем отзыв в базе данных
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reviews (location_id, user_id, rating, review_text)
        SELECT %s, id, %s, %s FROM users WHERE name = %s
    """, (location_id, rating, review_text, username))
    conn.commit()
    conn.close()

    return redirect(url_for('location_info', location_id=location_id))

if __name__ == '__main__':
    app.run(debug=True)
