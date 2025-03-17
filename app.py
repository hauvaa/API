from click import confirm
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import secrets
from flask_cors import CORS
import os
import uuid  # Để tạo session_id duy nhất
import json

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')
CORS(app)

DATABASE = 'database.db'

# Helper: Kết nối database
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Route: Đăng ký
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Kiểm tra confirm_password và password có khớp không
        if password != confirm_password:
            return "Mật khẩu và xác nhận mật khẩu không khớp", 400

        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Username đã tồn tại", 400
        finally:
            conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

# Route: Đăng nhập
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            return redirect(url_for('home'))
        else:
            return "Sai tên đăng nhập hoặc mật khẩu", 400

    return render_template('login.html')

@app.route('/logout', methods=['GET'])
def logout():
    # Xóa user_id khỏi session
    session.pop('user_id', None)
    return redirect(url_for('login'))

# Route: Xem các API keys của người dùng
@app.route('/view_api_keys', methods=['GET'])
def view_api_keys():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()

    # Lấy tất cả API keys của người dùng
    api_keys = conn.execute("SELECT api_key FROM api_keys WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()

    # Nếu không có API key nào
    if not api_keys:
        return render_template('home.html', message="Không có API keys nào được tạo.")

    # Trả về các API keys trong template
    return render_template('home.html', api_keys=[row['api_key'] for row in api_keys])

# Route: Trang chủ
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

# Route: Tạo API key
@app.route('/create_project', methods=['POST'])
def create_project():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    api_key = secrets.token_hex(32)

    conn = get_db_connection()
    conn.execute("INSERT INTO api_keys (user_id, api_key) VALUES (?, ?)", (user_id, api_key))
    conn.commit()
    conn.close()

    return render_template('api_info.html', api_key=api_key)

@app.route('/api/questions', methods=['POST'])
def send_questions():
    api_key = request.headers.get('x-api-key')
    conn = get_db_connection()

    # Kiểm tra xem api_key có hợp lệ không
    key_exists = conn.execute("SELECT * FROM api_keys WHERE api_key = ?", (api_key,)).fetchone()
    if not key_exists:
        conn.close()
        return jsonify({"error": "Invalid API key"}), 403

    # Nhận bộ câu hỏi từ request
    questions = request.get_json()

    # Kiểm tra nếu không có câu hỏi
    if not questions:
        conn.close()
        return jsonify({"error": "No questions provided"}), 400

    # Tạo client_id cho phiên chơi
    client_id = str(uuid.uuid4())

    # Kiểm tra và lưu câu hỏi vào bảng questions và session_questions
    for question in questions:
        question_id = question['id']
        question_text = question['question']

        # Kiểm tra xem câu hỏi đã tồn tại chưa
        existing_question = conn.execute(
            "SELECT * FROM questions WHERE api_key = ? AND id = ? AND question = ?",
            (api_key, question_id, question_text)
        ).fetchone()

        if not existing_question:
            conn.execute(
                "INSERT INTO questions (api_key, id, question) VALUES (?, ?, ?)",
                (api_key, question_id, question_text)
            )

        # Lưu câu hỏi vào bảng session_questions
        conn.execute(
            "INSERT INTO session_questions (client_id, question_id, question) VALUES (?, ?, ?)",
            (client_id, question_id, question_text)
        )

    conn.commit()

    # Lưu session vào bảng client_sessions
    conn.execute("INSERT INTO client_sessions (client_id, api_key) VALUES (?, ?)", (client_id, api_key))
    conn.commit()
    conn.close()

    # Trả lại đường link game cho khách hàng
    game_url = url_for('game_page', client_id=client_id, _external=True)

    return jsonify({"game_url": game_url, "client_id": client_id})

@app.route('/game')
def game_page():
    client_id = request.args.get('client_id', '')

    # Kết nối vào cơ sở dữ liệu
    conn = get_db_connection()

    # Kiểm tra session và lấy api_key
    session = conn.execute("SELECT api_key FROM client_sessions WHERE client_id = ?", (client_id,)).fetchone()
    if not session:
        conn.close()
        return "Session không hợp lệ", 400

    api_key = session["api_key"]

    # Lấy câu hỏi từ bảng session_questions theo client_id
    questions = conn.execute("SELECT question_id as id, question FROM session_questions WHERE client_id = ?", (client_id,)).fetchall()

    # Đóng kết nối cơ sở dữ liệu
    conn.close()

    # Chuyển đổi câu hỏi thành danh sách các từ điển
    questions_list = [dict(row) for row in questions]

    # Kiểm tra câu hỏi trước khi trả về
    print("Questions from DB:", questions_list)
    print(json.dumps(questions_list))

    # Trả lại câu hỏi cho game
    if questions_list:
        return render_template('index.html', client_id=client_id, api_key=api_key, questions=questions_list)
    else:
        return "Không có câu hỏi", 400

@app.route('/api_docs')
def api_docs():
    return render_template('api_docs.html')  # Trang hướng dẫn API


if __name__ == '__main__':
    app.run(debug=True)
