# from flask import Flask, render_template, request, session, redirect, url_for, flash
# #from flask_session import Session
# import requests
# import json
# import google.generativeai as genai
# import time
# import os
# from datetime import timedelta

# app = Flask(__name__)
# app.secret_key = '12000'
# app.config['SESSION_TYPE'] = 'filesystem'
# app.config['SESSION_FILE_DIR'] = './flask_session'
# app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
# #Session(app)

# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# model = genai.GenerativeModel("gemini-1.5-flash")

# USER_FILE = 'user.json'
# INTERVIEW_TREE_FILE = 'interview_tree.json'
# FEEDBACK_DIR = 'feedback'

# os.makedirs(FEEDBACK_DIR, exist_ok=True)
# os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)


# def load_data():
#     with open(INTERVIEW_TREE_FILE) as f:
#         tree = json.load(f)

#     if not os.path.exists(USER_FILE):
#         with open(USER_FILE, 'w') as f:
#             json.dump({}, f)

#     with open(USER_FILE) as f:
#         users = json.load(f)
#     return tree, users


# tree, users = load_data()


# def save_users():
#     with open(USER_FILE, 'w') as f:
#         json.dump(users, f)


# def find_node(node_id):
#     return next((n for n in tree['nodes'] if n['nodeId'] == node_id), None)


# def save_feedback(username, feedback_data):
#     filename = os.path.join(FEEDBACK_DIR, f"{username}_{int(time.time())}.json")
#     with open(filename, 'w') as f:
#         json.dump(feedback_data, f)
#     return filename


# def load_feedback(username):
#     feedback_files = [f for f in os.listdir(FEEDBACK_DIR) if f.startswith(username)]
#     if not feedback_files:
#         return None
#     latest_file = max(feedback_files)
#     with open(os.path.join(FEEDBACK_DIR, latest_file)) as f:
#         return json.load(f)


# @app.route('/', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']

#         if username in users and users[username] == password:
#             session.clear()
#             session['username'] = username
#             session['current_node'] = 'root'
#             session['start_time'] = time.time()
#             return redirect(url_for('interview'))
#         else:
#             return render_template('index.html', error="Invalid credentials")

#     return render_template('index.html')


# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']
#         confirm_password = request.form['confirm_password']

#         if not username or not password:
#             return render_template('register.html', error="Username and password are required")
#         if password != confirm_password:
#             return render_template('register.html', error="Passwords do not match")
#         if len(password) < 6:
#             return render_template('register.html', error="Password must be at least 6 characters")
#         if username in users:
#             return render_template('register.html', error="Username already exists")

#         users[username] = password
#         save_users()

#         flash('Registration successful! Please log in.', 'success')
#         return redirect(url_for('login'))

#     return render_template('register.html')


# def evaluate_all_answers(conversation):
#     if not conversation:
#         return [], 0

#     total_score = 0
#     valid_responses = 0
#     feedback_items = []

#     for item in conversation:
#         if (item["type"] == 'info') or (item["type"] == 'verification'):
#             continue
#         try:
#             prompt = f"""
#             Analyze this technical interview response as an easy interviewer, don't deduct ratings on 
#             grammar and formal/informal language usages and 
#             judge it keeping some room for mistake by candidate and be little lenient:
#             Question: {item.get('question', '')}
#             Answer: {item.get('answer', '')}

#             Provide:
#             1. Score (1-10) where 10 is excellent and 1 is poor
#             2. Brief feedback (1-2 sentences)
#             3. List of strengths
#             4. List of improvements

#             Return the response in this exact JSON format:
#             {{
#                 "score": 1-10,
#                 "brief_feedback": "Your feedback here",
#                 "strengths": ["strength1", "strength2"],
#                 "improvements": ["improvement1", "improvement2"]
#             }}
#             """

#             response = model.generate_content(prompt)
#             json_str = response.text.strip()

#             if json_str.startswith('```json'):
#                 json_str = json_str[7:]
#             if json_str.endswith('```'):
#                 json_str = json_str[:-3]
#             json_str = json_str.strip()

#             feedback = json.loads(json_str)

#             if not isinstance(feedback, dict):
#                 raise ValueError("Feedback is not a dictionary")

#             feedback['score'] = max(1, min(10, int(feedback.get('score'))))
#             feedback['brief_feedback'] = feedback.get('brief_feedback', "No feedback available")
#             feedback['strengths'] = feedback.get('strengths', [])
#             feedback['improvements'] = feedback.get('improvements', [])

#             total_score += feedback['score']
#             valid_responses += 1

#             feedback_items.append({
#                 'question': item.get('question', ''),
#                 'answer': item.get('answer', ''),
#                 **feedback
#             })

#         except Exception as e:
#             app.logger.error(f"Error evaluating answer: {str(e)}")
#             feedback_items.append({
#                 'question': item.get('question', ''),
#                 'answer': item.get('answer', ''),
#                 'score': 10,
#                 'brief_feedback': "Evaluation not available",
#                 'strengths': [],
#                 'improvements': []
#             })

#     avg_score = total_score / valid_responses if valid_responses > 0 else 0
#     return feedback_items, avg_score


# def generate_verdict(avg_score, duration, total_questions):
#     if duration < 5:
#         return {
#             'verdict': "NOT SELECTED",
#             'reason': "Interview ended too quickly",
#             'color': "red"
#         }
#     elif total_questions < 3:
#         return {
#             'verdict': "NOT SELECTED",
#             'reason': "Incomplete interview",
#             'color': "red"
#         }
#     elif avg_score >= 8:
#         return {
#             'verdict': "SELECTED",
#             'reason': "Excellent performance",
#             'color': "green"
#         }
#     elif avg_score >= 6:
#         return {
#             'verdict': "CONSIDER",
#             'reason': "Good but needs improvement",
#             'color': "yellow"
#         }
#     elif avg_score >= 4:
#         return {
#             'verdict': "MARGINAL",
#             'reason': "Below average performance",
#             'color': "orange"
#         }
#     else:
#         return {
#             'verdict': "NOT SELECTED",
#             'reason': "Poor performance",
#             'color': "red"
#         }


# @app.route('/interview', methods=['GET', 'POST'])
# def interview():
#     if 'username' not in session:
#         return redirect(url_for('login'))

#     if session.get('interview_complete'):
#         return redirect(url_for('report'))

#     current_node = find_node(session.get('current_node', 'root'))
#     conversation = session.get('conversation', [])

#     if request.method == 'POST':
#         if request.form.get('action') == 'end_interview':
#             session['interview_complete'] = True
#             return redirect(url_for('end_interview'))

#         user_answer = request.form.get('answer', '').strip()
#         if not user_answer:
#             flash('Please provide an answer', 'error')
#             return redirect(url_for('interview'))

#         conversation.append({
#             'type': current_node['type'],
#             'question': current_node['prompt'],
#             'answer': user_answer,
#             'feedback': ""
#         })
#         session['conversation'] = conversation

#         if 'edges' in current_node and current_node['edges']:
#             try:
#                 evaluation_prompt = f"""Classify the response into one of 
#                 {[e['condition'] for e in current_node['edges']]}
#                 based on the response to the question. 
#                 Return only the exact matching condition text:
#                 Question: {current_node['prompt']}
#                 Response: {user_answer}"""
#                 text_response = model.generate_content(evaluation_prompt)
#                 text_response_dict = text_response.to_dict()
#                 condition = text_response_dict.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get(
#                     "text", "").strip()

#                 matched_edge = next((e for e in current_node['edges'] if e['condition'] == condition), None)
#                 session['current_node'] = matched_edge['targetNodeId'] if matched_edge else current_node['edges'][0][
#                     'targetNodeId']

#             except Exception as e:
#                 app.logger.error(f"Error in interview flow: {e}")
#                 session['current_node'] = current_node['edges'][0]['targetNodeId']

#             current_node = find_node(session['current_node'])

#         if current_node is None:
#             session['interview_complete'] = True
#             return redirect(url_for('end_interview'))

#     total_nodes = len([n for n in tree['nodes'] if 'edges' in n])
#     completed_nodes = len(conversation)
#     progress = min(100, (completed_nodes / max(1, total_nodes // 2)) * 100)

#     return render_template('interview.html',
#                            question=current_node['prompt'],
#                            conversation=conversation,
#                            progress=progress)


# @app.route('/end-interview')
# def end_interview():
#     if 'username' not in session:
#         return redirect(url_for('login'))

#     try:
#         session['duration'] = (time.time() - session.get('start_time', time.time())) / 60
#         conversation = session.pop('conversation', [])

#         feedback_items, avg_score = evaluate_all_answers(conversation)
#         save_feedback(session['username'], {
#             'feedback': feedback_items,
#             'avg_score': avg_score,
#             'duration': session['duration']
#         })

#         session.update({
#             'feedback_generated': True,
#             'avg_score': avg_score,
#             'interview_complete': True
#         })

#         return redirect(url_for('report'))

#     except Exception as e:
#         app.logger.error(f"Error in end_interview: {e}")
#         flash('An error occurred while generating your report', 'error')
#         return redirect(url_for('report'))


# @app.route('/report')
# def report():
#     if 'username' not in session:
#         return redirect(url_for('login'))

#     try:
#         feedback_data = load_feedback(session['username'])
#         if not feedback_data:
#             flash('No feedback data found', 'error')
#             return redirect(url_for('interview'))

#         verdict = generate_verdict(
#             feedback_data['avg_score'],
#             feedback_data['duration'],
#             len(feedback_data['feedback'])
#         )

#         return render_template('report.html',
#                                username=session['username'],
#                                feedback=feedback_data['feedback'],
#                                verdict=verdict,
#                                duration=feedback_data['duration'],
#                                avg_score=feedback_data['avg_score'],
#                                completed=True)

#     except Exception as e:
#         app.logger.error(f"Error generating report: {e}")
#         flash('An error occurred while generating your report', 'error')
#         return redirect(url_for('interview'))


# if __name__ == '__main__':
#     app.run()




# app.py
# Vercel-compatible Flask app using Vercel KV for storage.
# - No local file writes (avoids Errno 30 on Vercel)
# - Uses interview_tree.json from the repo (read-only)
# - Cookie sessions (no filesystem sessions)
# - Requires env vars: GEMINI_API_KEY, FLASK_SECRET_KEY, plus Vercel KV config set in Vercel dashboard

from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
import json
import os
import time
import logging
from datetime import timedelta

# External clients
import google.generativeai as genai
from vercel_kv import KV

# --- App setup -------------------------------------------------------------
app = Flask(__name__)
# Use a secret key from env (set FLASK_SECRET_KEY in Vercel env)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "replace_this_in_prod")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Gemini model setup ---------------------------------------------------
# Make sure GEMINI_API_KEY is set in Vercel env (GEMINI_API_KEY)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# --- Vercel KV init -------------------------------------------------------
kv = KV()  # requires KV_URL and KV_REST_API_TOKEN set in Vercel environment

# --- Files / constants ----------------------------------------------------
INTERVIEW_TREE_FILE = "interview_tree.json"  # read-only file stored in repo

# --- Helper functions (KV-backed) ----------------------------------------

def load_tree():
    """Load interview tree from the repo (read-only)."""
    try:
        with open(INTERVIEW_TREE_FILE, "r") as f:
            tree = json.load(f)
        return tree
    except FileNotFoundError:
        logger.exception("%s not found in project root.", INTERVIEW_TREE_FILE)
        raise
    except Exception:
        logger.exception("Failed to load interview tree.")
        raise

def load_users():
    """Return dict of users {username: password}."""
    try:
        users = kv.get("users")
        return users if isinstance(users, dict) else {}
    except Exception:
        logger.exception("Error loading users from KV.")
        return {}

def save_users(users_dict):
    """Persist users dict to KV."""
    try:
        kv.set("users", users_dict)
    except Exception:
        logger.exception("Error saving users to KV.")
        raise

def save_feedback(username, feedback_data):
    """
    Append feedback_data to a list at key feedback:{username} and store latest snapshot
    at feedback_latest:{username}. Returns a reference string.
    """
    try:
        key_list = f"feedback:{username}"
        existing = kv.get(key_list) or []
        existing.append({
            "timestamp": int(time.time()),
            **feedback_data
        })
        kv.set(key_list, existing)
        kv.set(f"feedback_latest:{username}", existing[-1])
        return f"kv://{key_list}"
    except Exception:
        logger.exception("Error saving feedback to KV.")
        raise

def load_feedback(username):
    """Load latest feedback for username (tries latest key if available)."""
    try:
        latest = kv.get(f"feedback_latest:{username}")
        if latest:
            return latest
        all_fb = kv.get(f"feedback:{username}") or []
        return all_fb[-1] if all_fb else None
    except Exception:
        logger.exception("Error loading feedback from KV.")
        return None

# --- Load immutable tree and initial users --------------------------------
tree = load_tree()
# users is loaded fresh from KV to avoid stale state across invocations
users = load_users()

# --- Utility functions ----------------------------------------------------

def find_node(node_id):
    """Return node dict from tree by nodeId."""
    return next((n for n in tree.get("nodes", []) if n.get("nodeId") == node_id), None)

def evaluate_all_answers(conversation):
    """
    For each conversational item, ask Gemini to produce a JSON feedback structure.
    If model parsing fails, fallback to safe defaults.
    Returns (feedback_items, avg_score).
    """
    if not conversation:
        return [], 0

    total_score = 0
    valid_responses = 0
    feedback_items = []

    for item in conversation:
        if item.get("type") in ("info", "verification"):
            continue

        prompt = f"""
Analyze this technical interview response as an easy interviewer (be lenient).
Question: {item.get('question', '')}
Answer: {item.get('answer', '')}

Return exact JSON:
{{
  "score": <integer 1-10>,
  "brief_feedback": "<1-2 sentence feedback>",
  "strengths": ["..."],
  "improvements": ["..."]
}}
"""
        try:
            resp = model.generate_content(prompt)
            # .text should contain the model string; guard for formatting like ```json ... ```
            json_str = getattr(resp, "text", None)
            if not json_str:
                # Try dict-style access (some SDKs return structured candidates)
                try:
                    resp_dict = resp.to_dict()
                    json_str = resp_dict.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                except Exception:
                    json_str = ""

            json_str = (json_str or "").strip()
            # strip triple backticks if present
            if json_str.startswith("```json"):
                json_str = json_str[len("```json"):].strip()
            if json_str.startswith("```"):
                json_str = json_str[3:].strip()
            if json_str.endswith("```"):
                json_str = json_str[:-3].strip()

            feedback = json.loads(json_str)
            if not isinstance(feedback, dict):
                raise ValueError("Parsed feedback is not a dict")
            # sanitize fields
            score = int(feedback.get("score", 10))
            score = max(1, min(10, score))
            feedback_item = {
                "question": item.get("question", ""),
                "answer": item.get("answer", ""),
                "score": score,
                "brief_feedback": feedback.get("brief_feedback", "No feedback available"),
                "strengths": feedback.get("strengths", []),
                "improvements": feedback.get("improvements", [])
            }
            total_score += score
            valid_responses += 1
            feedback_items.append(feedback_item)

        except Exception as e:
            logger.exception("Evaluation failed for an answer: %s", e)
            # fallback safe feedback
            fallback = {
                "question": item.get("question", ""),
                "answer": item.get("answer", ""),
                "score": 10,
                "brief_feedback": "Evaluation not available",
                "strengths": [],
                "improvements": []
            }
            feedback_items.append(fallback)
            total_score += fallback["score"]
            valid_responses += 1

    avg_score = total_score / valid_responses if valid_responses else 0
    return feedback_items, avg_score

def generate_verdict(avg_score, duration_minutes, total_questions):
    """Simple verdict logic based on score, time, and number of questions."""
    if duration_minutes < 5:
        return {"verdict": "NOT SELECTED", "reason": "Interview ended too quickly", "color": "red"}
    elif total_questions < 3:
        return {"verdict": "NOT SELECTED", "reason": "Incomplete interview", "color": "red"}
    elif avg_score >= 8:
        return {"verdict": "SELECTED", "reason": "Excellent performance", "color": "green"}
    elif avg_score >= 6:
        return {"verdict": "CONSIDER", "reason": "Good but needs improvement", "color": "yellow"}
    elif avg_score >= 4:
        return {"verdict": "MARGINAL", "reason": "Below average performance", "color": "orange"}
    else:
        return {"verdict": "NOT SELECTED", "reason": "Poor performance", "color": "red"}

# --- Routes ---------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def login():
    # load latest users from KV to avoid stale local copy
    global users
    users = load_users()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username in users and users[username] == password:
            session.clear()
            session["username"] = username
            session["current_node"] = "root"
            session["start_time"] = time.time()
            session.permanent = True
            return redirect(url_for("interview"))
        else:
            return render_template("index.html", error="Invalid credentials")

    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not password:
            return render_template("register.html", error="Username and password are required")
        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match")
        if len(password) < 6:
            return render_template("register.html", error="Password must be at least 6 characters")

        # reload users to avoid races
        all_users = load_users()
        if username in all_users:
            return render_template("register.html", error="Username already exists")

        all_users[username] = password
        save_users(all_users)

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/interview", methods=["GET", "POST"])
def interview():
    if "username" not in session:
        return redirect(url_for("login"))

    # Protect against accidental redirect loops by ensuring we don't auto-redirect on errors.
    if session.get("interview_complete"):
        return redirect(url_for("report"))

    current_node = find_node(session.get("current_node", "root"))
    conversation = session.get("conversation", [])

    if request.method == "POST":
        action = request.form.get("action")
        if action == "end_interview":
            session["interview_complete"] = True
            # Use 303 to indicate POST->GET (optional)
            return redirect(url_for("end_interview"), code=303)

        user_answer = request.form.get("answer", "").strip()
        if not user_answer:
            flash("Please provide an answer", "error")
            return redirect(url_for("interview"))

        conversation.append({
            "type": current_node.get("type"),
            "question": current_node.get("prompt"),
            "answer": user_answer,
            "feedback": ""
        })
        session["conversation"] = conversation

        # If current node has branching edges, ask model to classify which edge to take
        if "edges" in current_node and current_node["edges"]:
            try:
                conditions = [e.get("condition", "") for e in current_node["edges"]]
                evaluation_prompt = f"""Classify the response into one of {conditions} and return exactly the matching condition text.
Question: {current_node.get('prompt')}
Response: {user_answer}
"""
                text_response = model.generate_content(evaluation_prompt)
                # extract text robustly
                condition_text = ""
                try:
                    # try to read .text
                    condition_text = getattr(text_response, "text", "") or ""
                    if not condition_text and hasattr(text_response, "to_dict"):
                        tdict = text_response.to_dict()
                        condition_text = tdict.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                except Exception:
                    condition_text = ""

                condition = condition_text.strip()
                matched_edge = next((e for e in current_node["edges"] if e.get("condition") == condition), None)
                if matched_edge:
                    session["current_node"] = matched_edge.get("targetNodeId")
                else:
                    # default to first edge if none matched
                    session["current_node"] = current_node["edges"][0].get("targetNodeId")
            except Exception as e:
                logger.exception("Error in interview flow: %s", e)
                # fallback to default branch
                session["current_node"] = current_node["edges"][0].get("targetNodeId")

            current_node = find_node(session.get("current_node"))

        if current_node is None:
            session["interview_complete"] = True
            return redirect(url_for("end_interview"))

    # progress calculation (safe guard divide)
    total_nodes = len([n for n in tree.get("nodes", []) if "edges" in n])
    completed_nodes = len(conversation)
    progress = min(100, (completed_nodes / max(1, total_nodes // 2)) * 100)

    return render_template("interview.html",
                           question=current_node.get("prompt") if current_node else "No question",
                           conversation=conversation,
                           progress=progress)


@app.route("/end-interview")
def end_interview():
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        # duration in minutes
        start_time = session.get("start_time", time.time())
        duration_minutes = (time.time() - start_time) / 60.0
        conversation = session.pop("conversation", [])

        feedback_items, avg_score = evaluate_all_answers(conversation)
        # save feedback into KV
        save_feedback(session["username"], {
            "feedback": feedback_items,
            "avg_score": avg_score,
            "duration": duration_minutes
        })

        session.update({
            "feedback_generated": True,
            "avg_score": avg_score,
            "interview_complete": True,
            "duration": duration_minutes
        })

        return redirect(url_for("report"))
    except Exception as e:
        logger.exception("Error in end_interview: %s", e)
        # don't redirect into a loop on error; render a simple error page or show flash
        flash("An error occurred while generating your report", "error")
        return render_template("error.html", message="Failed to generate report"), 500


@app.route("/report")
def report():
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        feedback_data = load_feedback(session["username"])
        if not feedback_data:
            flash("No feedback data found", "error")
            # render interview page instead of redirect loop
            return render_template("interview.html", question=find_node(session.get("current_node", "root")).get("prompt"),
                                   conversation=session.get("conversation", []), progress=0)

        verdict = generate_verdict(
            feedback_data.get("avg_score", 0),
            feedback_data.get("duration", 0),
            len(feedback_data.get("feedback", []))
        )

        return render_template("report.html",
                               username=session["username"],
                               feedback=feedback_data.get("feedback", []),
                               verdict=verdict,
                               duration=feedback_data.get("duration", 0),
                               avg_score=feedback_data.get("avg_score", 0),
                               completed=True)
    except Exception as e:
        logger.exception("Error generating report: %s", e)
        flash("An error occurred while generating your report", "error")
        return render_template("error.html", message="Failed to generate report"), 500


# --- Run locally ----------------------------------------------------------
if __name__ == "__main__":
    # Local dev: ensure environment variables are set or mocked for local testing.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

