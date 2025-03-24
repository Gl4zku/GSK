from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
from deep_translator import GoogleTranslator

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    news = db.relationship('News', backref='author', lazy=True)

class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    preview_image = db.Column(db.String(100), nullable=True)
    content_images = db.Column(db.Text, nullable=True)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    translated_content = db.Column(db.Text, nullable=True)

# Helpers
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


translations = {
    'ru': {
        'add_news': 'Добавить новость',
        'home': 'Главная',
        'profile': 'Профиль',
        'logout': 'Выйти',
        'admin_panel': 'Админ Панель',
        'login': 'Вход',
        'register': 'Регистрация',
        'last_news': 'Последние новости',
        'no_news': 'Новостей пока нет',
        'published_on': 'Опубликовано',
        'submit': 'Отправить',
        'email_in_use': 'Этот email уже используется',
        'translate': 'Перевести'
    },
    'en': {
        'add_news': 'Add News',
        'home': 'Home',
        'profile': 'Profile',
        'logout': 'Logout',
        'admin_panel': 'Admin Panel',
        'login': 'Login',
        'register': 'Register',
        'last_news': 'Last News',
        'no_news': 'No news available',
        'published_on': 'Published on',
        'submit': 'Submit',
        'email_in_use': 'This email is already in use',
        'translate': 'Translate'
    },
    'es': {
        'add_news': 'Agregar noticia',
        'home': 'Inicio',
        'profile': 'Perfil',
        'logout': 'Salir',
        'admin_panel': 'Panel de administración',
        'login': 'Iniciar sesión',
        'register': 'Registrarse',
        'last_news': 'Últimas noticias',
        'no_news': 'No hay noticias disponibles',
        'published_on': 'Publicado el',
        'submit': 'Enviar',
        'email_in_use': 'Este correo ya está en uso',
        'translate': 'Traducir'
    },
    'zh': {
        'add_news': '添加新闻',
        'home': '主页',
        'profile': '个人资料',
        'logout': '退出',
        'admin_panel': '管理面板',
        'login': '登录',
        'register': '注册',
        'last_news': '最新消息',
        'no_news': '暂无新闻',
        'published_on': '发布于',
        'submit': '提交',
        'email_in_use': '此电子邮件已被使用',
        'translate': '翻译'
    }
}

def translate(key):
    language = session.get('language', 'en')
    return translations.get(language, translations['en']).get(key, key)

@app.context_processor
def inject_translations():
    return {'t': translate}

@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return {'current_user': user}

@app.route('/set_language', methods=['POST'])
def set_language():
    language = request.form.get('language', 'en')
    if language not in translations:
        flash("Выбранный язык не поддерживается.", "error")
    else:
        session['language'] = language
        flash(f"Язык переключен на {translations[language]['home']}.", "info")
    return redirect(request.referrer or '/')


@app.route('/news/<int:news_id>/translate', methods=['POST'])
def translate_news(news_id):
    news = News.query.get_or_404(news_id)
    target_language = session.get('language', 'en')

    language_codes = {
        'ru': 'ru',
        'en': 'en',
        'es': 'es',
        'zh': 'zh-CN'
    }

    if target_language not in language_codes:
        flash('Выбранный язык не поддерживается.', 'error')
        return redirect(url_for('news_detail', news_id=news_id))

    try:
        translated_text = GoogleTranslator(source='ru', target=language_codes[target_language]).translate(news.content)
        
        news.translated_content = translated_text
        db.session.commit()
        flash('Новость успешно переведена.', 'success')
    except Exception as e:
        flash(f'Ошибка перевода: {str(e)}', 'error')

    return redirect(url_for('news_detail', news_id=news_id))



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
            flash(translate('email_in_use'), 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        user_count = User.query.count()
        role = 'superadmin' if user_count == 0 else 'user'
        new_user = User(email=email, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash(translate('register_success'), 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':    
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session.permanent = True  # Сессия сохраняется на длительное время
            session['user_id'] = user.id
            flash('Вы вошли в систему.', 'success')
            return redirect(url_for('profile'))  # Перенаправление на профиль
        else:
            flash('Неправильный email или пароль.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Вы вышли из системы.', 'success')
    return redirect(url_for('login'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('Сначала войдите в систему.', 'error')
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    user_news = News.query.filter_by(author_id=user.id).all()
    return render_template('profile.html', user=user, news=user_news)

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        flash('Сначала войдите в систему.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        preview_image = request.files.get('preview_image')
        content_images = request.files.getlist('content_images')

        preview_filename = None
        if preview_image and allowed_file(preview_image.filename):
            preview_filename = secure_filename(preview_image.filename)
            preview_image.save(os.path.join(app.config['UPLOAD_FOLDER'], preview_filename))

        content_filenames = []
        for image in content_images:
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                content_filenames.append(filename)

        new_news = News(
            title=title,
            content=content,
            preview_image=preview_filename,
            content_images=','.join(content_filenames),
            author_id=session['user_id']
        )
        db.session.add(new_news)
        db.session.commit()
        flash('Новость добавлена!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('dashboard.html')

@app.route('/news/<int:news_id>')
def news_detail(news_id):
    news = News.query.get_or_404(news_id)
    news.views += 1
    db.session.commit()
    return render_template('news_detail.html', news=news)


if __name__ == '__main__':  
    with app.app_context():
        db.create_all()
    app.run(debug=True)
