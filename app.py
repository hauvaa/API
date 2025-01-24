from click import confirm
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import secrets
from flask_cors import CORS
import os
import uuid  # Để tạo session_id duy nhất

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
    key_exists = conn.execute("SELECT * FROM api_keys WHERE api_key = ?", (api_key,)).fetchone()

    if not key_exists:
        conn.close()
        return jsonify({"error": "Invalid API key"}), 403

    # Lấy thông tin bộ câu hỏi
    data = request.json
    questions = data.get('questions', [])

    client_id = str(uuid.uuid4())

    # Lưu thông tin vào bảng client_sessions
    conn.execute("INSERT INTO client_sessions (client_id, api_key) VALUES (?, ?)", (client_id, api_key))
    conn.commit()
    conn.close()

    # Tạo form HTML
    form_html = '''
    <html>
    <head><title>Answer the Questions</title></head>
    <body>
        <h1>Answer the Questions</h1>
        <form id="answerForm" onsubmit="submitAnswers(event)">
    '''

    for q in questions:
        form_html += f'''
        <label>{q["question"]}</label><br>
        <input type="text" name="question_{q["id"]}" required><br><br>
        '''

    form_html += '''
            <button type="submit">Submit Answers</button>
        </form>
    </body>
    </html>
    '''

    # Trả về client_id và form
    return jsonify({"form_html": form_html, "client_id": client_id})

# Route: Submit answers
@app.route('/api/submit_answers/<client_id>', methods=['POST'])
def submit_answers(client_id):
    api_key = request.headers.get('x-api-key')
    conn = get_db_connection()

    # Kiểm tra API key hợp lệ
    key_exists = conn.execute("SELECT * FROM api_keys WHERE api_key = ?", (api_key,)).fetchone()
    if not key_exists:
        conn.close()
        return jsonify({"error": "Invalid API key"}), 403

    # Kiểm tra client_id hợp lệ
    client_session = conn.execute("SELECT * FROM client_sessions WHERE client_id = ?", (client_id,)).fetchone()
    if not client_session:
        conn.close()
        return jsonify({"error": "Invalid client ID"}), 403

    # Lấy câu trả lời từ request
    data = request.json
    try:
        # Lưu câu trả lời vào database
        for question_id, answer in data.items():
            conn.execute("INSERT INTO answers (client_id, question_id, answer) VALUES (?, ?, ?)",
                         (client_id, question_id, answer))
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({"error": "Failed to save answers"}), 500

    conn.close()
    return jsonify({"status": "completed"})

# Route: Get answers
@app.route('/api/answers/<client_id>', methods=['GET'])
def get_answers(client_id):
    api_key = request.headers.get('x-api-key')
    conn = get_db_connection()

    # Kiểm tra API key hợp lệ
    key_exists = conn.execute("SELECT * FROM api_keys WHERE api_key = ?", (api_key,)).fetchone()
    if not key_exists:
        conn.close()
        return jsonify({"error": "Invalid API key"}), 403

    # Kiểm tra client_id hợp lệ
    client_session = conn.execute("SELECT * FROM client_sessions WHERE client_id = ?", (client_id,)).fetchone()
    if not client_session:
        conn.close()
        return jsonify({"error": "Invalid client ID"}), 403

    # Lấy câu trả lời từ database
    answers = conn.execute("SELECT question_id, answer FROM answers WHERE client_id = ?", (client_id,)).fetchall()
    conn.close()

    if not answers:
        return jsonify({"status": "no_answers"}), 404

    # Trả về danh sách câu trả lời
    answers_list = [{"id": row["question_id"], "answer": row["answer"]} for row in answers]
    return jsonify({"status": "completed", "answers": answers_list})


if __name__ == '__main__':
    app.run(debug=True)
