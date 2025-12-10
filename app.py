from flask import Flask, render_template, request, session, redirect, url_for, flash
#from flask_session import Session
import requests
import json
import google.generativeai as genai
import time
import os
from datetime import timedelta

app = Flask(__name__)
app.secret_key = '12000'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './flask_session'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
#Session(app)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

USER_FILE = 'user.json'
INTERVIEW_TREE_FILE = 'interview_tree.json'
FEEDBACK_DIR = 'feedback'

os.makedirs(FEEDBACK_DIR, exist_ok=True)
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)


def load_data():
    with open(INTERVIEW_TREE_FILE) as f:
        tree = json.load(f)

    if not os.path.exists(USER_FILE):
        with open(USER_FILE, 'w') as f:
            json.dump({}, f)

    with open(USER_FILE) as f:
        users = json.load(f)
    return tree, users


tree, users = load_data()


def save_users():
    with open(USER_FILE, 'w') as f:
        json.dump(users, f)


def find_node(node_id):
    return next((n for n in tree['nodes'] if n['nodeId'] == node_id), None)


def save_feedback(username, feedback_data):
    filename = os.path.join(FEEDBACK_DIR, f"{username}_{int(time.time())}.json")
    with open(filename, 'w') as f:
        json.dump(feedback_data, f)
    return filename


def load_feedback(username):
    feedback_files = [f for f in os.listdir(FEEDBACK_DIR) if f.startswith(username)]
    if not feedback_files:
        return None
    latest_file = max(feedback_files)
    with open(os.path.join(FEEDBACK_DIR, latest_file)) as f:
        return json.load(f)


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username in users and users[username] == password:
            session.clear()
            session['username'] = username
            session['current_node'] = 'root'
            session['start_time'] = time.time()
            return redirect(url_for('interview'))
        else:
            return render_template('index.html', error="Invalid credentials")

    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if not username or not password:
            return render_template('register.html', error="Username and password are required")
        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match")
        if len(password) < 6:
            return render_template('register.html', error="Password must be at least 6 characters")
        if username in users:
            return render_template('register.html', error="Username already exists")

        users[username] = password
        save_users()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


def evaluate_all_answers(conversation):
    if not conversation:
        return [], 0

    total_score = 0
    valid_responses = 0
    feedback_items = []

    for item in conversation:
        if (item["type"] == 'info') or (item["type"] == 'verification'):
            continue
        try:
            prompt = f"""
            Analyze this technical interview response as an easy interviewer, don't deduct ratings on 
            grammar and formal/informal language usages and 
            judge it keeping some room for mistake by candidate and be little lenient:
            Question: {item.get('question', '')}
            Answer: {item.get('answer', '')}

            Provide:
            1. Score (1-10) where 10 is excellent and 1 is poor
            2. Brief feedback (1-2 sentences)
            3. List of strengths
            4. List of improvements

            Return the response in this exact JSON format:
            {{
                "score": 1-10,
                "brief_feedback": "Your feedback here",
                "strengths": ["strength1", "strength2"],
                "improvements": ["improvement1", "improvement2"]
            }}
            """

            response = model.generate_content(prompt)
            json_str = response.text.strip()

            if json_str.startswith('```json'):
                json_str = json_str[7:]
            if json_str.endswith('```'):
                json_str = json_str[:-3]
            json_str = json_str.strip()

            feedback = json.loads(json_str)

            if not isinstance(feedback, dict):
                raise ValueError("Feedback is not a dictionary")

            feedback['score'] = max(1, min(10, int(feedback.get('score'))))
            feedback['brief_feedback'] = feedback.get('brief_feedback', "No feedback available")
            feedback['strengths'] = feedback.get('strengths', [])
            feedback['improvements'] = feedback.get('improvements', [])

            total_score += feedback['score']
            valid_responses += 1

            feedback_items.append({
                'question': item.get('question', ''),
                'answer': item.get('answer', ''),
                **feedback
            })

        except Exception as e:
            app.logger.error(f"Error evaluating answer: {str(e)}")
            feedback_items.append({
                'question': item.get('question', ''),
                'answer': item.get('answer', ''),
                'score': 10,
                'brief_feedback': "Evaluation not available",
                'strengths': [],
                'improvements': []
            })

    avg_score = total_score / valid_responses if valid_responses > 0 else 0
    return feedback_items, avg_score


def generate_verdict(avg_score, duration, total_questions):
    if duration < 5:
        return {
            'verdict': "NOT SELECTED",
            'reason': "Interview ended too quickly",
            'color': "red"
        }
    elif total_questions < 3:
        return {
            'verdict': "NOT SELECTED",
            'reason': "Incomplete interview",
            'color': "red"
        }
    elif avg_score >= 8:
        return {
            'verdict': "SELECTED",
            'reason': "Excellent performance",
            'color': "green"
        }
    elif avg_score >= 6:
        return {
            'verdict': "CONSIDER",
            'reason': "Good but needs improvement",
            'color': "yellow"
        }
    elif avg_score >= 4:
        return {
            'verdict': "MARGINAL",
            'reason': "Below average performance",
            'color': "orange"
        }
    else:
        return {
            'verdict': "NOT SELECTED",
            'reason': "Poor performance",
            'color': "red"
        }


@app.route('/interview', methods=['GET', 'POST'])
def interview():
    if 'username' not in session:
        return redirect(url_for('login'))

    if session.get('interview_complete'):
        return redirect(url_for('report'))

    current_node = find_node(session.get('current_node', 'root'))
    conversation = session.get('conversation', [])

    if request.method == 'POST':
        if request.form.get('action') == 'end_interview':
            session['interview_complete'] = True
            return redirect(url_for('end_interview'))

        user_answer = request.form.get('answer', '').strip()
        if not user_answer:
            flash('Please provide an answer', 'error')
            return redirect(url_for('interview'))

        conversation.append({
            'type': current_node['type'],
            'question': current_node['prompt'],
            'answer': user_answer,
            'feedback': ""
        })
        session['conversation'] = conversation

        if 'edges' in current_node and current_node['edges']:
            try:
                evaluation_prompt = f"""Classify the response into one of 
                {[e['condition'] for e in current_node['edges']]}
                based on the response to the question. 
                Return only the exact matching condition text:
                Question: {current_node['prompt']}
                Response: {user_answer}"""
                text_response = model.generate_content(evaluation_prompt)
                text_response_dict = text_response.to_dict()
                condition = text_response_dict.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get(
                    "text", "").strip()

                matched_edge = next((e for e in current_node['edges'] if e['condition'] == condition), None)
                session['current_node'] = matched_edge['targetNodeId'] if matched_edge else current_node['edges'][0][
                    'targetNodeId']

            except Exception as e:
                app.logger.error(f"Error in interview flow: {e}")
                session['current_node'] = current_node['edges'][0]['targetNodeId']

            current_node = find_node(session['current_node'])

        if current_node is None:
            session['interview_complete'] = True
            return redirect(url_for('end_interview'))

    total_nodes = len([n for n in tree['nodes'] if 'edges' in n])
    completed_nodes = len(conversation)
    progress = min(100, (completed_nodes / max(1, total_nodes // 2)) * 100)

    return render_template('interview.html',
                           question=current_node['prompt'],
                           conversation=conversation,
                           progress=progress)


@app.route('/end-interview')
def end_interview():
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        session['duration'] = (time.time() - session.get('start_time', time.time())) / 60
        conversation = session.pop('conversation', [])

        feedback_items, avg_score = evaluate_all_answers(conversation)
        save_feedback(session['username'], {
            'feedback': feedback_items,
            'avg_score': avg_score,
            'duration': session['duration']
        })

        session.update({
            'feedback_generated': True,
            'avg_score': avg_score,
            'interview_complete': True
        })

        return redirect(url_for('report'))

    except Exception as e:
        app.logger.error(f"Error in end_interview: {e}")
        flash('An error occurred while generating your report', 'error')
        return redirect(url_for('report'))


@app.route('/report')
def report():
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        feedback_data = load_feedback(session['username'])
        if not feedback_data:
            flash('No feedback data found', 'error')
            return redirect(url_for('interview'))

        verdict = generate_verdict(
            feedback_data['avg_score'],
            feedback_data['duration'],
            len(feedback_data['feedback'])
        )

        return render_template('report.html',
                               username=session['username'],
                               feedback=feedback_data['feedback'],
                               verdict=verdict,
                               duration=feedback_data['duration'],
                               avg_score=feedback_data['avg_score'],
                               completed=True)

    except Exception as e:
        app.logger.error(f"Error generating report: {e}")
        flash('An error occurred while generating your report', 'error')
        return redirect(url_for('interview'))


if __name__ == '__main__':
    app.run()
