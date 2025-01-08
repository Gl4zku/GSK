import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import logging
from datetime import datetime

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = 'your_secret_key'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

ROLES = ['user', 'moder', 'admin', 'superadmin']

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')

class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    preview_image = db.Column(db.String(100), nullable=True)
    content_images = db.Column(db.Text, nullable=True)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


def role_required(role):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                flash('Вы должны войти в систему.', 'error')
                return redirect(url_for('login'))
            user = User.query.get(session['user_id'])
            if ROLES.index(user.role) < ROLES.index(role):
                flash('Недостаточно прав доступа.', 'error')
                return redirect(url_for('index'))
            return func(*args, **kwargs)
        return wrapper
    return decorator

@app.context_processor
def inject_user():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        return dict(current_user=user)
    return dict(current_user=None)

@app.route('/')
def index():
    news = News.query.order_by(News.created_at.desc()).all()
    return render_template('index.html', news=news)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('Этот email уже зарегистрирован.', 'error')
            return redirect(url_for('register'))
        
        # Проверка количества пользователей для назначения роли superadmin
        first_user = User.query.first()
        role = 'superadmin' if not first_user else 'user'
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(email=email, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()
        session['user_id'] = new_user.id
        flash('Регистрация успешна. Добро пожаловать!', 'success')
        return redirect(url_for('profile'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Вы успешно вошли.', 'success')
            return redirect(url_for('profile'))
        flash('Неверный email или пароль.', 'error')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Вы успешно вышли из аккаунта.', 'success')
    return redirect(url_for('index'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('Сначала войдите в систему.', 'error')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        flash('Пользователь не найден.', 'error')
        return redirect(url_for('login'))

    news = News.query.filter_by(author_id=user.id).all()  # Получаем новости пользователя
    return render_template('profile.html', user=user, news=news)

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        flash('Сначала войдите в систему.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        preview_image = request.files.get('preview_image')

        preview_filename = None
        if preview_image and allowed_file(preview_image.filename):
            filename = secure_filename(preview_image.filename)
            preview_image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            preview_filename = filename
        
        # Проверка на авторизацию и добавление автор_id
        if 'user_id' in session:
            author_id = session['user_id']
        else:
            flash('Ошибка: Пользователь не авторизован.', 'error')
            return redirect(url_for('login'))
        
        # Добавляем новость в базу данных
        new_news = News(
            title=title,
            content=content,
            preview_image=preview_filename,
            author_id=session['user_id']  # Устанавливаем автора новости
        )
        db.session.add(new_news)
        db.session.commit()
        flash('Новость добавлена!', 'success')
        return redirect(url_for('profile'))
    
    news = News.query.all()
    return render_template('dashboard.html', news=news)


@app.route('/admin_panel')
@role_required('admin')
def admin_panel():
    users = User.query.all()
    return render_template('admin_panel.html', users=users)

@app.route('/news/<int:news_id>')
def view_news(news_id):
    news_item = News.query.get_or_404(news_id)
    news_item.views += 1
    db.session.commit()
    content_images = news_item.content_images.split(',') if news_item.content_images else []
    return render_template('news.html', news=news_item, content_images=content_images)

@app.route('/edit_news/<int:news_id>', methods=['GET', 'POST'])
def edit_news(news_id):
    if 'user_id' not in session:
        flash('Сначала войдите в систему.', 'error')
        return redirect(url_for('login'))
    
    news_item = News.query.get_or_404(news_id)
    
    # Проверка владельца новости
    if news_item.author_id != session['user_id']:
        flash('Вы не можете редактировать эту новость.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        news_item.title = request.form['title']
        news_item.content = request.form['content']
        
        # Обновление изображения при необходимости
        preview_image = request.files.get('preview_image')
        if preview_image and allowed_file(preview_image.filename):
            filename = secure_filename(preview_image.filename)
            preview_image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            news_item.preview_image = filename
        
        db.session.commit()
        flash('Новость успешно отредактирована.', 'success')
        return redirect(url_for('view_news', news_id=news_item.id))
    
    return render_template('edit_news.html', news=news_item)


if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    with app.app_context():
        db.create_all()

    app.run(debug=True)
