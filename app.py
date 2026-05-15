from flask import Flask, request, jsonify, send_from_directory
import json, sqlite3, random, os, datetime

app = Flask(__name__, static_folder='.', static_url_path='')
# CORS removed - not needed for same-origin deployment on PythonAnywhere

DB_PATH = 'exam.db'
QUESTIONS_PATH = 'questions.json'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        total_score INTEGER,
        correct_count INTEGER,
        wrong_count INTEGER,
        time_spent INTEGER,
        submit_time TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        score_id INTEGER,
        question_id INTEGER,
        question_text TEXT,
        question_type TEXT,
        options TEXT,
        correct_answer TEXT,
        user_answer TEXT,
        is_correct INTEGER,
        score INTEGER
    )''')
    conn.commit()
    conn.close()

init_db()

def load_questions():
    with open(QUESTIONS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)['questions']

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/admin')
def admin():
    return send_from_directory('.', 'admin.html')

@app.route('/api/questions', methods=['GET'])
def get_questions():
    questions = load_questions()
    random.shuffle(questions)
    for q in questions:
        if q['type'] in ('single', 'multi') and 'options' in q:
            original = q['options'][:]
            random.shuffle(q['options'])
            if q['type'] == 'single':
                old_letter = q['answer'][0]
                idx = ord(old_letter) - 65
                if idx < len(original):
                    txt = original[idx]
                    for i, opt in enumerate(q['options']):
                        if opt == txt:
                            q['answer'] = [chr(65 + i)]
                            break
            else:
                new_answer = []
                for old_letter in q['answer']:
                    idx = ord(old_letter) - 65
                    if idx < len(original):
                        txt = original[idx]
                        for i, opt in enumerate(q['options']):
                            if opt == txt:
                                new_answer.append(chr(65 + i))
                                break
                q['answer'] = new_answer
    return jsonify({'questions': questions})

@app.route('/api/submit', methods=['POST'])
def submit():
    data = request.json
    name = data.get('name', '匿名')
    answers = data.get('answers', [])
    time_spent = data.get('time_spent', 0)
    questions = {q['id']: q for q in load_questions()}

    correct_count = 0
    wrong_count = 0
    total_score = 0
    answer_records = []

    for ans in answers:
        qid = ans['question_id']
        q = questions.get(qid)
        if not q:
            continue
        is_correct = 0
        if q['type'] == 'judge':
            user_ans = ans.get('answer', [''])[0]
            is_correct = 1 if user_ans == q['answer'] else 0
        else:
            user_ans = sorted(ans.get('answer', []))
            correct_ans = sorted(q['answer'])
            is_correct = 1 if user_ans == correct_ans else 0

        if is_correct:
            correct_count += 1
            total_score += q['score']
        else:
            wrong_count += 1

        answer_records.append({
            'question_id': qid,
            'question_text': q['question'],
            'question_type': q['type'],
            'options': json.dumps(q.get('options', []), ensure_ascii=False),
            'correct_answer': json.dumps(q['answer'], ensure_ascii=False),
            'user_answer': json.dumps(ans.get('answer', []), ensure_ascii=False),
            'is_correct': is_correct,
            'score': q['score'] if is_correct else 0
        })

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'INSERT INTO scores (name, total_score, correct_count, wrong_count, time_spent, submit_time) VALUES (?,?,?,?,?,?)',
        (name, total_score, correct_count, wrong_count, time_spent, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    score_id = c.lastrowid
    for rec in answer_records:
        c.execute(
            'INSERT INTO answers (score_id, question_id, question_text, question_type, options, correct_answer, user_answer, is_correct, score) VALUES (?,?,?,?,?,?,?,?,?)',
            (score_id, rec['question_id'], rec['question_text'], rec['question_type'],
             rec['options'], rec['correct_answer'], rec['user_answer'], rec['is_correct'], rec['score'])
        )
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'score_id': score_id, 'total_score': total_score, 'correct_count': correct_count, 'wrong_count': wrong_count})

@app.route('/api/scores', methods=['GET'])
def get_scores():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, name, total_score, correct_count, wrong_count, time_spent, submit_time FROM scores ORDER BY id DESC')
    rows = c.fetchall()
    conn.close()
    result = []
    for r in rows:
        mins = r[5] // 60
        secs = r[5] % 60
        result.append({
            'id': r[0], 'name': r[1], 'total_score': r[2],
            'correct_count': r[3], 'wrong_count': r[4],
            'time_spent': f"{mins}分{secs}秒",
            'submit_time': r[6]
        })
    return jsonify({'scores': result})

@app.route('/api/scores/<int:score_id>/details', methods=['GET'])
def get_details(score_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM answers WHERE score_id = ?', (score_id,))
    rows = c.fetchall()
    conn.close()
    cols = ['id', 'score_id', 'question_id', 'question_text', 'question_type', 'options', 'correct_answer', 'user_answer', 'is_correct', 'score']
    result = []
    for r in rows:
        d = dict(zip(cols, r))
        d['options'] = json.loads(d['options']) if d['options'] else []
        d['correct_answer'] = json.loads(d['correct_answer']) if d['correct_answer'] else []
        d['user_answer'] = json.loads(d['user_answer']) if d['user_answer'] else []
        result.append(d)
    return jsonify({'details': result})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*), AVG(total_score), MAX(total_score), MIN(total_score) FROM scores')
    r = c.fetchone()
    c.execute('SELECT name, total_score FROM scores ORDER BY total_score DESC LIMIT 5')
    top5 = c.fetchall()
    conn.close()
    return jsonify({
        'count': r[0], 'avg_score': round(r[1] or 0, 1),
        'max_score': r[2] or 0, 'min_score': r[3] or 0,
        'top5': [{'name': t[0], 'score': t[1]} for t in top5]
    })

@app.route('/api/clear-data', methods=['DELETE'])
def clear_data():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM answers')
    c.execute('DELETE FROM scores')
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': '所有数据已清理'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
