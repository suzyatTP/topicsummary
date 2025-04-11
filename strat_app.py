from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import os
import io
import json
import psycopg2

from werkzeug.security import generate_password_hash, check_password_hash
from flask import session

app = Flask(__name__)
def get_db_connection():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))
app.secret_key = 'your_secret_key_here'
DB_FILE = 'drafts.db'

def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # Create users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Update drafts table to associate drafts with users
    c.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, user_id)
        )
    """)

    conn.commit()
    conn.close()

init_db()

# --- Helper functions for DB ---

import uuid
from flask import make_response

def get_or_create_user_id():
    user_id = request.cookies.get('user_id')
    if not user_id:
        # generate new UUID
        user_id = str(uuid.uuid4())

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = %s", (user_id,))
    user = c.fetchone()
    if user:
        db_user_id = user[0]
    else:
        c.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
            (user_id, generate_password_hash("temporary"))
        )
        db_user_id = c.fetchone()[0]
        conn.commit()
    conn.close()

    # Store the UUID as a cookie in the response later
    request.user_cookie_id = user_id  # store temporarily for response to use
    return db_user_id

def save_draft_to_db(name, content_dict):
    user_id = get_or_create_user_id()
    conn = get_db_connection()
    c = conn.cursor()
    json_data = json.dumps(content_dict)
    c.execute("""
        INSERT INTO drafts (name, content, user_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (name, user_id)
        DO UPDATE SET content = EXCLUDED.content,
                      updated_at = CURRENT_TIMESTAMP
    """, (name, json_data, user_id))
    conn.commit()
    conn.close()

def load_draft_from_db(name):
    user_id = get_or_create_user_id()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT content FROM drafts WHERE name = %s AND user_id = %s", (name, user_id))
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return {}

def list_drafts():
    user_id = get_or_create_user_id()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM drafts WHERE user_id = %s", (user_id,))
    drafts = [row[0] for row in c.fetchall()]
    conn.close()
    return drafts

def delete_draft(name):
    user_id = get_or_create_user_id()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM drafts WHERE name = %s AND user_id = %s", (name, user_id))
    conn.commit()
    conn.close()

# --- PDF utilities ---
def draw_wrapped_text(p, x, y, text, max_width, font_name=None, font_size=None, line_height=14):
    if font_name and font_size:
        p.setFont(font_name, font_size)
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + " " + word if current_line else word
        if p.stringWidth(test_line, font_name, font_size) <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    for line in lines:
        p.drawString(x, y, line)
        y -= line_height
    return len(lines) * line_height

def get_text_height(text, max_width, font_name="Helvetica", font_size=10, line_height=14):
    dummy = canvas.Canvas(io.BytesIO())
    dummy.setFont(font_name, font_size)
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + " " + word if current_line else word
        if dummy.stringWidth(test_line, font_name, font_size) <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return line_height * len(lines) + 10

# --- Routes ---
@app.route('/', methods=['GET'])
def form():
    draft_name = request.args.get("draft")
    data = load_draft_from_db(draft_name) if draft_name else {}
    response = make_response(render_template('form.html', data=data, drafts=list_drafts(), selected_draft=draft_name))

    if hasattr(request, 'user_cookie_id'):
        response.set_cookie('user_id', request.user_cookie_id, max_age=60*60*24*365)  # 1 year

    return response

@app.route('/submit', methods=['POST'])
def submit():
    data = request.form.to_dict()
    action = data.get("action")
    draft_name = data.get("draft_name")

    if action == "save":
        if not draft_name:
            flash("Please enter a name for your draft.")
            response = make_response(redirect(url_for('form')))
        else:
            save_draft_to_db(draft_name, data)
            flash(f"Draft '{draft_name}' saved successfully.")
            response = make_response(redirect(url_for('form', draft=draft_name)))
        if hasattr(request, 'user_cookie_id'):
            response.set_cookie('user_id', request.user_cookie_id, max_age=60 * 60 * 24 * 365)
        return response

    elif action == "delete":
        if draft_name:
            delete_draft(draft_name)
            flash(f"Draft '{draft_name}' has been deleted.")
        response = make_response(redirect(url_for('form')))
        if hasattr(request, 'user_cookie_id'):
            response.set_cookie('user_id', request.user_cookie_id, max_age=60 * 60 * 24 * 365)
        return response

    elif action == "submit":
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Simple header
        p.setFillColorRGB(0.15, 0.18, 0.25)
        p.rect(0, height - 70, width, 70, fill=1, stroke=0)
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, height - 30, "Turning Point for God")
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, "Strategic / Ad hoc Topic Summary")

        p.showPage()
        p.save()
        buffer.seek(0)

        pdf_filename = f"{draft_name or 'Strategic_Topic_Summary'}.pdf"
        return send_file(buffer, as_attachment=True, download_name=pdf_filename, mimetype='application/pdf')

    return redirect(url_for('form'))

if __name__ == '__main__':
    app.run(debug=True)
