from flask import Flask, render_template, url_for, request, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_required, login_user, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from os.path import join, dirname, realpath
import os
import upload

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'secret key'
app.config['MAX_CONTENT_PATH'] = 20000000
app.config['UPLOAD_FOLDER'] = join(dirname(realpath(__file__)), 'static/images/..')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class Post(db.Model, UserMixin):
    title = db.Column(db.String(300))
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    filename = db.Column(db.String(300), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    likes = db.relationship('Like', backref='post', lazy='dynamic')

    def __repr__(self):
        return '<Post %r>' % self.id


@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).get(user_id)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(64), nullable=False)
    is_admin = db.Column(db.Boolean, default=0)
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    liked = db.relationship('Like', foreign_keys='Like.user_id', backref='user', lazy='dynamic')

    profile_data = db.relationship('Profile_data', backref='user', uselist=False)

    def like_post(self, post):
        if not self.has_liked_post(post):
            like = Like(user_id=self.id, post_id=post.id)
            db.session.add(like)

    def unlike_post(self, post):
        if self.has_liked_post(post):
            Like.query.filter_by(
                user_id=self.id,
                post_id=post.id).delete()

    def has_liked_post(self, post):
        return Like.query.filter(
            Like.user_id == self.id,
            Like.post_id == post.id).count() > 0

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def __repr__(self):
        return "{}".format(self.username)

    def get_id(self):
        return self.id


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))


class Profile_data(db.Model):
    gender = db.Column(db.String(50), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    hobby = db.Column(db.String(50), nullable=False)
    contacts = db.Column(db.String(50), nullable=False)

    user_id = db.Column(db.Integer(), db.ForeignKey('user.id'), primary_key=True)


@app.route('/')
@app.route('/home')
def home():
    logged_user = User.query.get(current_user.get_id())
    posts = Post.query.order_by(Post.id.desc()).all()
    users = User.query.order_by(User.id.desc())
    return render_template("home.html", posts=posts, users=users, logged_user=logged_user)


@app.route('/like/<int:post_id>/<action>')
@login_required
def like_action(post_id, action):
    post = Post.query.filter_by(id=post_id).first_or_404()
    if action == 'like':
        current_user.like_post(post)
        db.session.commit()
    if action == 'unlike':
        current_user.unlike_post(post)
        db.session.commit()
    return redirect(request.referrer)


@app.route('/delete/<int:post_id>')
@login_required
def delete_post(post_id):
    if not User.query.get(current_user.get_id()).is_admin:
        return '<h2>Вы не обладаете правами администратора</h2><br><a href ="/home">Вернуться</a>'

    Post.query.filter_by(id=post_id).delete()
    Like.query.filter_by(post_id=post_id).delete()
    db.session.commit()

    return redirect('/home')


@app.route('/new_post', methods=['POST', 'GET'])
@login_required
def new_post():
    logged_user = User.query.get(current_user.get_id())
    upload_message = ''
    if request.method == 'POST':
        file = request.files['file']
        title = request.form['title']
        if file and upload.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            new_post_db = Post(title=title, filename=filename, user_id=current_user.get_id())
            db.session.add(new_post_db)
            db.session.commit()
            return redirect('/home')
        else:
            upload_message = 'Ваш фаел маст би jpg png или gif. Андерстэнд?'
    return render_template("new_post.html", upload_message=upload_message, logged_user=logged_user)


@app.route('/login', methods=['POST', 'GET'])
def login():
    logged_user = User.query.get(current_user.get_id())
    if current_user.is_authenticated:
        return redirect('/home')
    message = ''
    if request.method == 'POST':
        print(request.form)
        username = request.form.get('username')
        password = request.form.get('password')

        user_to_login = db.session.query(User).filter(User.username == username).first()
        try:
            if user_to_login.check_password(password):
                login_user(user_to_login)
                return redirect('/home')
            else:
                message = "Неверное имя пользователя или пароль"
        except:
            message = "Неверное имя пользователя или пароль"

    return render_template("login.html", message=message, logged_user=logged_user)


@app.route('/register', methods=['POST', 'GET'])
def register():
    logged_user = User.query.get(current_user.get_id())
    if current_user.is_authenticated:
        return redirect('/home')

    message = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')

        age = request.form.get('age')
        gender = request.form.get('gender')
        hobby = request.form.get('hobby')
        contacts = request.form.get('contacts')

        if username == '' or password == '' or email == '' or age == '' or hobby == '' or contacts == '':
            message = 'Проверьте корректность данных'
            return render_template("register.html", message=message)

        if str(db.session.query(User).filter(User.username == username).first()) != str(username):
            new_user_db = User(username=username, email=email)
            new_user_db.set_password(password)
            db.session.add(new_user_db)
            db.session.commit()

            new_profile_db = Profile_data(age=age, gender=gender, hobby=hobby, contacts=contacts,
                                          user_id=new_user_db.id)
            db.session.add(new_profile_db)
            db.session.commit()

            return redirect('/login')
        else:
            message = 'Пользователь с таким именем уже существует'

    return render_template("register.html", message=message, logged_user=logged_user)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/home')


@app.route('/profile_edit', methods=['POST', 'GET'])
@login_required
def profile_edit():
    logged_user = User.query.get(current_user.get_id())
    profile_data = Profile_data.query.get(current_user.get_id())
    user_data = User.query.get(current_user.get_id())
    message = ''

    if request.method == 'POST':
        username = request.form.get('username')
        age = request.form.get('age')
        gender = request.form.get('gender')
        hobby = request.form.get('hobby')
        contacts = request.form.get('contacts')

        if username == '' or age == '' or hobby == '' or contacts == '':
            message = 'Проверьте корректность данных'
            return render_template("profile_edit.html", profile_data=profile_data, user=user_data, message=message)

        if str(db.session.query(User).filter(User.username == username).first()) == str(username) and db.session.query(
                User).filter(User.username == username).first().id != current_user.get_id():
            message = 'Пользователь с таким именем уже существует'
            return render_template("profile_edit.html", profile_data=profile_data, user=user_data, message=message)

        edited_user = db.session.query(User).get(current_user.get_id())
        edited_user.username = username
        db.session.commit()

        edited_profile = db.session.query(Profile_data).get(current_user.get_id())
        edited_profile.age = age
        edited_profile.gender = gender
        edited_profile.hobby = hobby
        edited_profile.contacts = contacts
        db.session.commit()
        return redirect('/user/' + str(current_user.get_id()))

    return render_template("profile_edit.html", profile_data=profile_data, user=user_data, message=message, logged_user=logged_user)


@app.route('/user/<int:user_id>')
@login_required
def user(user_id):
    logged_user = User.query.get(current_user.get_id())
    profile_data = Profile_data.query.get(user_id)
    user_data = User.query.get(user_id)

    show_overlap = False
    if Like.query.filter_by(user_id=current_user.get_id()).count() >= 3 and current_user.get_id() == user_id:
        show_overlap = True

    if user_data is None:
        return '<h2>Похоже, такого пользователя не существует</h2><br><a href ="/home">Вернуться</a>'
    return render_template("user.html", profile_data=profile_data, user=user_data, show_overlap=show_overlap, logged_user=logged_user)


@app.route('/admin_panel', methods=['POST', 'GET'])
@login_required
def admin_panel():
    logged_user = User.query.get(current_user.get_id())
    if not User.query.get(current_user.get_id()).is_admin:
        return '<h2>Вы не обладаете правами администратора</h2><br><a href ="/home">Вернуться</a>'

    message = ''
    users = User.query.order_by(User.id.desc()).all()

    if request.method == 'POST':
        users_to_delete = ['#']
        for user_id in range(1, User.query.order_by(User.id.desc()).first().id + 1):
            if str(request.form.get('delete'+str(user_id))) == 'on':
                users_to_delete.append(user_id)

        for user_to_delete in users_to_delete:
            User.query.filter_by(id=user_to_delete).delete()
            Profile_data.query.filter_by(user_id=user_to_delete).delete()
            db.session.commit()
        message = 'Пользователи успешно удалены'

    users = User.query.order_by(User.id.desc()).all()
    return render_template("admin_panel.html", users=users, message=message, logged_user=logged_user)


@app.route('/overlap')
@login_required
def overlap():
    logged_user = User.query.get(current_user.get_id())
    if Like.query.filter_by(user_id=current_user.get_id()).count() < 3:
        return '<h2>Вы должны лайкнуть как минимум 3 поста, чтобы получить совпадения</h2><br><a href ="/home">Вернуться</a>'
    message = ''

    overlaps = []
    users = User.query.order_by(User.id.desc()).all()
    for user_to_check in users:
        if user_to_check.id != current_user.get_id():
            overlaps.append([0, user_to_check.id, user_to_check.username])

    for user_to_check in overlaps:
        user_id = user_to_check[1]
        user_likes = Like.query.filter_by(user_id=user_id).all()
        for like in user_likes:
            if Like.query.filter_by(user_id=current_user.get_id(), post_id=like.post_id).count()>0:
                user_to_check[0] += 1
    overlaps.sort(reverse=True)

    print(overlaps)
    count = min([len(overlaps), 5])
    return render_template("overlap.html", message=message, overlaps=overlaps, count=count, logged_user=logged_user)


if __name__ == "__main__":
    app.run(debug=True)
