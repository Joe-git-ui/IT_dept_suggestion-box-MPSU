from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import datetime
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///suggestion_box.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class Suggestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    date_submitted = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    reviewed = db.Column(db.Boolean, default=False)
    archived = db.Column(db.Boolean, default=False)
    profanity_flagged = db.Column(db.Boolean, default=False)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

class ProfanityWord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), unique=True, nullable=False)

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    profanity_filter_enabled = db.Column(db.Boolean, default=True)

# Decorator for admin login required
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    print("Serving updated index.html")
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit_suggestion():
    title = request.form.get('title')
    content = request.form.get('suggestion')
    category = request.form.get('category')

    if not title or title.strip() == '':
        flash('Title cannot be empty.', 'danger')
        return redirect(url_for('index'))

    if not content or content.strip() == '':
        flash('Suggestion cannot be empty.', 'danger')
        return redirect(url_for('index'))

    if not category or category.strip() == '':
        flash('Please select a category.', 'danger')
        return redirect(url_for('index'))

    settings = Settings.query.first()
    profanity_filter_enabled = settings.profanity_filter_enabled if settings else True

    profanity_words = [pw.word.lower() for pw in ProfanityWord.query.all()]
    content_lower = content.lower()
    if profanity_filter_enabled:
        blocked_words = [word for word in profanity_words if word in content_lower]
        if blocked_words:
            flash(f'Your suggestion was not submitted because it contains blocked words: {", ".join(blocked_words)}. Please revise and resubmit.', 'danger')
            return redirect(url_for('index'))

    suggestion = Suggestion(title=title, content=content, category=category)
    db.session.add(suggestion)
    db.session.commit()
    flash('Suggestion submitted successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('admin_register'))
        existing_admin = Admin.query.filter_by(username=username).first()
        if existing_admin:
            flash('Username already exists.', 'danger')
            return redirect(url_for('admin_register'))
        password_hash = generate_password_hash(password)
        new_admin = Admin(username=username, password_hash=password_hash)
        db.session.add(new_admin)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('admin_login'))
    return render_template('admin_register.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session['admin_id'] = admin.id
            flash('Logged in successfully.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('admin_login'))
    return render_template('admin_login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    session.pop('admin_id', None)
    flash('Logged out successfully.', 'success')
    return redirect(url_for('admin_login'))

from flask import send_file
import io
import csv
from math import ceil

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    sort_by = request.args.get('sort_by', 'date_desc')
    filter_reviewed = request.args.get('filter_reviewed', 'all')
    filter_profanity = request.args.get('filter_profanity', 'all')
    filter_category = request.args.get('filter_category', 'all')
    search_query = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 10

    suggestions_query = Suggestion.query.filter_by(archived=False)

    if filter_reviewed == 'reviewed':
        suggestions_query = suggestions_query.filter_by(reviewed=True)
    elif filter_reviewed == 'unreviewed':
        suggestions_query = suggestions_query.filter_by(reviewed=False)

    if filter_profanity == 'flagged':
        suggestions_query = suggestions_query.filter_by(profanity_flagged=True)
    elif filter_profanity == 'not_flagged':
        suggestions_query = suggestions_query.filter_by(profanity_flagged=False)

    if filter_category != 'all':
        suggestions_query = suggestions_query.filter_by(category=filter_category)

    if search_query:
        search_pattern = f"%{search_query}%"
        suggestions_query = suggestions_query.filter(
            (Suggestion.title.ilike(search_pattern)) | (Suggestion.content.ilike(search_pattern))
        )

    if sort_by == 'date_asc':
        suggestions_query = suggestions_query.order_by(Suggestion.date_submitted.asc())
    else:
        suggestions_query = suggestions_query.order_by(Suggestion.date_submitted.desc())

    total = suggestions_query.count()
    suggestions = suggestions_query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = ceil(total / per_page)

    settings = Settings.query.first()
    profanity_filter_enabled = settings.profanity_filter_enabled if settings else True

    categories = [c[0] for c in db.session.query(Suggestion.category).distinct().all()]

    return render_template('admin_dashboard.html', suggestions=suggestions, profanity_filter_enabled=profanity_filter_enabled,
                           total_pages=total_pages, current_page=page, categories=categories,
                           filter_category=filter_category, search_query=search_query)

@app.route('/admin/mark_reviewed/<int:suggestion_id>', methods=['POST'])
@login_required
def mark_reviewed(suggestion_id):
    suggestion = Suggestion.query.get_or_404(suggestion_id)
    suggestion.reviewed = True
    db.session.commit()
    flash('Suggestion marked as reviewed!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/unmark_reviewed/<int:suggestion_id>', methods=['POST'])
@login_required
def unmark_reviewed(suggestion_id):
    suggestion = Suggestion.query.get_or_404(suggestion_id)
    suggestion.reviewed = False
    db.session.commit()
    flash('Suggestion marked as unreviewed!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/<int:suggestion_id>', methods=['POST'])
@login_required
def delete_suggestion(suggestion_id):
    suggestion = Suggestion.query.get_or_404(suggestion_id)
    suggestion.archived = True
    db.session.commit()
    flash('Suggestion deleted/archived!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/permanent_delete/<int:suggestion_id>', methods=['POST'])
@login_required
def permanent_delete_suggestion(suggestion_id):
    suggestion = Suggestion.query.get_or_404(suggestion_id)
    db.session.delete(suggestion)
    db.session.commit()
    flash('Suggestion permanently deleted!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/export_csv')
@login_required
def export_csv():
    suggestions = Suggestion.query.filter_by(archived=False).all()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Unique ID', 'Title', 'Category', 'Content', 'Date Submitted', 'Reviewed', 'Profanity Flagged'])
    for s in suggestions:
        cw.writerow([s.unique_id, s.title, s.category, s.content, s.date_submitted.strftime('%Y-%m-%d %H:%M:%S'), s.reviewed, s.profanity_flagged])
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='suggestions.csv')

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    settings = Settings.query.first()
    if not settings:
        settings = Settings(profanity_filter_enabled=True)
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        profanity_filter_enabled = request.form.get('profanity_filter_enabled') == 'on'
        settings.profanity_filter_enabled = profanity_filter_enabled
        db.session.commit()
        flash('Settings updated!', 'success')
        return redirect(url_for('admin_settings'))

    profanity_words = ProfanityWord.query.order_by(ProfanityWord.word.asc()).all()
    return render_template('admin_settings.html', settings=settings, profanity_words=profanity_words)

@app.route('/admin/profanity/add', methods=['POST'])
@login_required
def add_profanity_word():
    word = request.form.get('word')
    if word:
        existing = ProfanityWord.query.filter_by(word=word.lower()).first()
        if not existing:
            new_word = ProfanityWord(word=word.lower())
            db.session.add(new_word)
            db.session.commit()
            flash(f'Word "{word}" added to profanity list.', 'success')
        else:
            flash(f'Word "{word}" already exists in profanity list.', 'warning')
    return redirect(url_for('admin_settings'))

@app.route('/admin/profanity/remove/<int:word_id>', methods=['POST'])
@login_required
def remove_profanity_word(word_id):
    word = ProfanityWord.query.get_or_404(word_id)
    db.session.delete(word)
    db.session.commit()
    flash(f'Word "{word.word}" removed from profanity list.', 'success')
    return redirect(url_for('admin_settings'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
