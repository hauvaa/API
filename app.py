from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Dữ liệu giả lập (có thể thay bằng database hoặc hệ thống lưu trữ khác)
sessions = {}  # Dùng để lưu trữ câu trả lời của từng session


# Endpoint 1: Nhận bộ câu hỏi từ web test và tạo form
@app.route('/questions', methods=['POST'])
def send_questions():
    data = request.json
    questions = data.get('questions', [])

    # Tạo session_id ngẫu nhiên hoặc sử dụng UUID
    session_id = "abc123"  # Giả lập session_id
    sessions[session_id] = {}

    # Tạo HTML form từ câu hỏi
    form_html = f'''
    <html>
    <head><title>Answer the Questions</title></head>
    <body>
        <h1>Answer the Questions</h1>
        <form id="answerForm" onsubmit="submitAnswers(event)">
    '''

    for q in questions:
        form_html += f'<label>{q["question"]}</label><br>'
        form_html += f'<input type="text" name="question_{q["id"]}" required><br><br>'

    form_html += '''
        <button type="submit">Submit Answers</button>
        </form>
    </body>
    </html>
    '''

    return jsonify({
        "status": "success",
        "session_id": session_id,
        "form_html": form_html
    })


# Endpoint 2: Nhận và lưu câu trả lời của người dùng
@app.route('/submit_answers/<session_id>', methods=['POST'])
def submit_answers(session_id):
    # Kiểm tra các giá trị gửi đến từ form
    answers = []
    for key, value in request.json.items():
        parts = key.split("_")
        if len(parts) == 2:  # Kiểm tra xem có đủ phần tử
            question_id = int(parts[1])  # Lấy id câu hỏi từ tên trường
            answers.append({"id": question_id, "answer": value})

    # Lưu câu trả lời vào session
    sessions[session_id] = answers

    # Trả lại câu trả lời cho web test
    return jsonify({
        "status": "completed",
        "session_id": session_id,
        "answers": answers
    })


# Endpoint 3: Lấy câu trả lời của người dùng từ session
@app.route('/answers/<session_id>', methods=['GET'])
def get_answers(session_id):
    answers = sessions.get(session_id, [])
    return jsonify({
        "status": "completed",
        "session_id": session_id,
        "answers": answers
    })


if __name__ == '__main__':
    app.run(debug=True)
