from flask import Flask, request, jsonify, render_template, redirect, url_for

app = Flask(__name__)

# Lưu trữ tạm thời câu trả lời (có thể thay bằng database)
answers_storage = {}

# Endpoint 1: Nhận bộ câu hỏi từ lập trình viên web
@app.route('/questions', methods=['POST'])
def send_questions():
    data = request.json
    questions = data.get('questions', [])

    # Tạo URL trả về form để người dùng trả lời
    session_id = "abc123"  # Tạo session_id ngẫu nhiên hoặc sử dụng UUID
    form_url = f"https://api-zyh1.onrender.com/form/{session_id}"

    # Lưu bộ câu hỏi vào storage
    answers_storage[session_id] = {"questions": questions, "answers": []}

    return jsonify({
        "status": "success",
        "session_id": session_id,
        "form_url": form_url
    })


# Endpoint 3: Hiển thị form trả lời
@app.route('/form/<session_id>', methods=['GET', 'POST'])
def form_page(session_id):
    if request.method == 'POST':
        # Lấy câu trả lời từ form
        answers = request.form.getlist('answers')
        stored_data = answers_storage.get(session_id)

        if stored_data:
            # Lưu câu trả lời vào storage
            for i, answer in enumerate(answers):
                stored_data['answers'].append({
                    "id": stored_data["questions"][i]["id"],
                    "answer": answer
                })

            return redirect(url_for('thank_you'))  # Chuyển đến trang cảm ơn

    # Lấy câu hỏi từ storage
    stored_data = answers_storage.get(session_id)
    if not stored_data:
        return "Session not found", 404

    questions = stored_data['questions']
    return render_template('form.html', questions=questions, session_id=session_id)


# Endpoint 4: Trang cảm ơn
@app.route('/thank-you', methods=['GET'])
def thank_you():
    return "<h1>Thank you for your answers!</h1>"


# Endpoint 2: Trả lời bộ câu hỏi
@app.route('/answers/<session_id>', methods=['GET'])
def get_answers(session_id):
    stored_data = answers_storage.get(session_id)
    if not stored_data:
        return jsonify({"status": "error", "message": "Session not found"}), 404

    return jsonify({
        "status": "completed",
        "session_id": session_id,
        "answers": stored_data["answers"]
    })


if __name__ == '__main__':
    app.run(debug=True)
