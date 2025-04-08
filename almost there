from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import os
import io
import json
import psycopg2

app = Flask(__name__)
def get_db_connection():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))
app.secret_key = 'your_secret_key_here'
DB_FILE = 'drafts.db'

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Helper functions for DB ---
def save_draft_to_db(name, content_dict):
    conn = get_db_connection()
    c = conn.cursor()
    json_data = json.dumps(content_dict)
    c.execute("""
        INSERT INTO drafts (name, content)
        VALUES (%s, %s)
        ON CONFLICT (name)
        DO UPDATE SET content = EXCLUDED.content
    """, (name, json_data))
    conn.commit()
    conn.close()

def load_draft_from_db(name):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT content FROM drafts WHERE name = %s", (name,))
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return {}

def list_drafts():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM drafts")
    drafts = [row[0] for row in c.fetchall()]
    conn.close()
    return drafts

def delete_draft(name):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM drafts WHERE name = %s", (name,))
    conn.commit()
    conn.close()

# --- PDF utilities ---
def draw_wrapped_text(p, x, y, text, max_width, font_name=None, font_size=None, line_height=14, top_padding=5, bottom_padding=5):
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

    # total height of the text block
    text_height = len(lines) * line_height
    total_padding = top_padding + bottom_padding

    # calculate vertical offset to center text inside the box
    offset = (total_padding + text_height) / 2

    # start drawing slightly lower to visually center
    y = y - offset + line_height

    for line in lines:
        p.drawString(x, y, line)
        y -= line_height

    return text_height + total_padding

def get_text_height(text, max_width, font_name="Helvetica", font_size=10, line_height=14, top_padding=5, bottom_padding=5):
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
    return (line_height * len(lines)) + top_padding + bottom_padding

# --- Routes ---
@app.route('/', methods=['GET'])
def form():
    draft_name = request.args.get("draft")
    data = load_draft_from_db(draft_name) if draft_name else {}
    return render_template('form.html', data=data, drafts=list_drafts(), selected_draft=draft_name)

@app.route('/submit', methods=['POST'])
def submit():
    data = request.form.to_dict()
    action = data.get("action")
    draft_name = data.get("draft_name")

    if action == "save":
        if not draft_name:
            flash("Please enter a name for your draft.")
        else:
            save_draft_to_db(draft_name, data)
            flash(f"Draft '{draft_name}' saved successfully.")
        return redirect(url_for('form', draft=draft_name))

    if action == "delete":
        if draft_name:
            delete_draft(draft_name)
            flash(f"Draft '{draft_name}' has been deleted.")
        return redirect(url_for('form'))

    # --- PDF Generation ---
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    p.setFillColorRGB(0.15, 0.18, 0.25)
    p.rect(0, height - 70, width, 70, fill=1, stroke=0)
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, height - 30, "Turning Point for God")
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, "Strategic / Ad hoc Topic Summary")
    logo_path = os.path.join("static", "overlay_icon.png")
    if os.path.exists(logo_path):
        p.drawImage(logo_path, width - 70, height - 60, width=40, height=40, mask='auto')

    p.setFillColor(colors.black)
    y = height - 90
    top_fields = [
        ("Topic", data.get("Topic", "")),
        ("Point Person", data.get("PointPerson", "")),
        ("Role of Executive Team (consult, inform, decide)", data.get("Role", "")),
        ("Executive Sponsor", data.get("Sponsor", "")),
        ("Problem Definition", data.get("Problem", "")),
        ("Outcome Description", data.get("Outcome", "")),
        ("Primary Recommendation", data.get("Recommendation", ""))
    ]
    for label, val in top_fields:
        box_height = get_text_height(val, width - 100, font_size=11, top_padding=5, bottom_padding=5)
        if y - box_height < 60:
            p.showPage()
            y = height - 50
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, label)
        p.rect(50, y - box_height - 5, width - 100, box_height, stroke=1, fill=0)
        p.setFont("Helvetica", 11)
        draw_wrapped_text(p, 55, y - 20, val, width - 110, font_name="Helvetica", font_size=11, top_padding=5, bottom_padding=5)
        y -= (box_height + 15)

    p.showPage()
    y = height - 90

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Options Table")
    y -= 20

    rows = [
        ("Description", [data.get("Option1Description", ""), data.get("Option2Description", ""), data.get("Option3Description", "")]),
        ("Pros", [data.get("Option1Pros", ""), data.get("Option2Pros", ""), data.get("Option3Pros", "")]),
        ("Cons", [data.get("Option1Cons", ""), data.get("Option2Cons", ""), data.get("Option3Cons", "")]),
        ("Benefits/Revenue", [data.get("Option1Benefits/Revenue", ""), data.get("Option2Benefits/Revenue", ""), data.get("Option3Benefits/Revenue", "")]),
        ("Obstacles", [data.get("Option1Obstacles", ""), data.get("Option2Obstacles", ""), data.get("Option3Obstacles", "")])
    ]
    col_width = (width - 100) / 4
    p.setFont("Helvetica-Bold", 11)
    p.rect(50, y - 20, col_width, 20, stroke=1, fill=0)
    for i, header in enumerate(["Option 1", "Option 2", "Option 3"]):
        x = 50 + col_width * (i + 1)
        p.rect(x, y - 20, col_width, 20, stroke=1, fill=0)
        p.drawCentredString(x + col_width / 2, y - 15, header)
    y -= 30

    for label, options in rows:
        heights = [get_text_height(txt, col_width - 10) for txt in options]
        row_h = max(heights) + 20
        if y - row_h < 60:
            p.showPage()
            y = height - 50
        p.setFont("Helvetica-Bold", 10)
        p.rect(50, y - row_h, col_width, row_h, stroke=1, fill=0)
        draw_wrapped_text(p, 55, y - 10, label, col_width - 10, font_name="Helvetica-Bold", font_size=11, top_padding=5, bottom_padding=5)
        for i in range(3):
            x = 50 + (i + 1) * col_width
            p.setFont("Helvetica", 11)
            p.rect(x, y - row_h, col_width, row_h, stroke=1, fill=0)
            draw_wrapped_text(p, x + 5, y - 20, options[i], col_width - 10)
        y -= (row_h + 10)
        y -= 8

    decision = data.get("Decision", "")
    box_height = get_text_height(decision, width - 100, font_size=11, top_padding=5, bottom_padding=5)
    if y - box_height < 60:
        p.showPage()
        y = height - 50
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Final Decision")
    p.rect(50, y - box_height - 5, width - 100, box_height, stroke=1, fill=0)
    p.setFont("Helvetica", 12)
    draw_wrapped_text(p, 55, y - 20, decision, width - 110, font_name="Helvetica", font_size=11, top_padding=5, bottom_padding=5)
    y -= (box_height + 15)
    y -= 20

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Key Actions: (Who, What, When?)")
    y -= 10
    for i in range(1, 6):
        action = data.get(f"Action{i}", "")
        box_height = get_text_height(action, width - 130, font_size=11, top_padding=5, bottom_padding=5)
        if y - box_height < 60:
            p.showPage()
            y = height - 50
        p.setFont("Helvetica-Bold", 10)
        p.drawString(55, y - 15, f"{i}.")
        p.rect(75, y - box_height - 5, width - 120, box_height, stroke=1, fill=0)
        p.setFont("Helvetica", 11)
        draw_wrapped_text(p, 80, y - 10, action, width - 130, font_name="Helvetica", font_size=11, top_padding=5, bottom_padding=5)
        y -= (box_height + 15)

    logo_path = os.path.join("static", "logo.png")
    if os.path.exists(logo_path):
        p.drawImage(logo_path, 50, 20, width=80, height=30, mask='auto')  # Adjust size/position as needed
     

    p.save()
    buffer.seek(0)
    pdf_filename = f"{draft_name or 'Strategic_Topic_Summary'}.pdf"
    return send_file(buffer, as_attachment=True, download_name=pdf_filename, mimetype='application/pdf')


if __name__ == '__main__':
    app.run(debug=True)