import os
import secrets
from PIL import Image
from flask import render_template as rt
from flask import url_for, flash, redirect, request, abort
from flask_login import login_user, current_user, logout_user, login_required
from flask import Flask, render_template, request, redirect, url_for, flash

from doctor import app, db, bcrypt
from doctor.helper import response, diagnose_text, dcnn
from doctor.models import User, Patient, Post
from doctor.forms import RegistrationForm, LoginForm, UpdateAccountForm, PatientForm, PostForm


@app.route('/')
@app.route('/home')
def home():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.date_posted.desc()).paginate(page=page, per_page=5)
    return rt("home.html", posts=posts)


@app.route('/diagnosis')
@login_required
def diagnosis():
    page = request.args.get('page', 1, type=int)
    patients = Patient.query.order_by(Patient.date.desc()).paginate(page=page, per_page=3)
    return rt("diagnosis.html", patients=patients)


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Welcome! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return rt('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Invalid email or password', 'danger')
    return rt('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))


def save_picture_profile(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_img', picture_fn)

    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn


@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture_profile(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_img/' + current_user.image_file)
    return rt('account.html', title='Account', image_file=image_file, form=form)


def save_picture_test(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/test_img', picture_fn)

    i = Image.open(form_picture)
    i.save(picture_path)
    return picture_fn


@app.route('/patient/new', methods=['GET', 'POST'])
@login_required
def new_patient():
    form = PatientForm()
    if form.validate_on_submit():
        picture_file = save_picture_test(form.picture.data)
        path = 'doctor/static/test_img/' + picture_file
        result = dcnn(path)
        diagnosis = diagnose_text(result)
        patient = Patient(firstname=form.firstname.data, lastname=form.lastname.data,
                          phone=form.phone.data, email=form.email.data, image_file=picture_file,
                          result=result, diagnosis=diagnosis, doctor=current_user)
        db.session.add(patient)
        db.session.commit()
        flash('New patient added!', 'success')
        return redirect(url_for('diagnosis'))
    return rt('create_patient.html', title='New Patient', form=form, legend='New Patient')


@app.route("/patient/<int:patient_id>")
@login_required
def patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    return rt('patient.html', title=patient.firstname, patient=patient)


@app.route("/user/<string:username>/patients")
def patients_user(username):
    page = request.args.get('page', 1, type=int)
    user = User.query.filter_by(username=username).first_or_404()
    patients = Patient.query.filter_by(doctor=user).order_by(Patient.date.desc()).paginate(page=page, per_page=3)
    return rt('patients_user.html', patients=patients, user=user)


@app.route("/patient/<int:patient_id>/update", methods=['GET', 'POST'])
@login_required
def update_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if patient.doctor != current_user:
        abort(403)
    form = PatientForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture_test(form.picture.data)
            path = 'doctor/static/test_img/' + picture_file
            result = dcnn(path)
            diagnosis = diagnose_text(result)
            patient.image_file = picture_file
            patient.result = result
            patient.diagnosis = diagnosis

        patient.firstname = form.firstname.data
        patient.lastname = form.lastname.data
        patient.phone = form.phone.data
        patient.email = form.email.data
        db.session.commit()
        flash('Patient information has been updated!', 'success')
        return redirect(url_for('patient', patient_id=patient.id))
    elif request.method == 'GET':
        form.firstname.data = patient.firstname
        form.lastname.data = patient.lastname
        form.phone.data = patient.phone
        form.email.data = patient.email
    image_file = url_for('static', filename='test_img/' + patient.image_file)
    return rt('create_patient.html', title='Update Patient', image_file=image_file, form=form, legend='Update Patient')


@app.route("/patient/<int:patient_id>/delete", methods=['POST'])
@login_required
def delete_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if patient.doctor != current_user:
        abort(403)
    db.session.delete(patient)
    db.session.commit()
    flash('Patient has been removed!', 'success')
    return redirect(url_for('diagnosis'))


@app.route("/post/new", methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content=form.content.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('New post created!', 'success')
        return redirect(url_for('home'))
    return rt('create_post.html', title='New Post', form=form, legend='New Post')


@app.route("/post/<int:post_id>")
def post(post_id):
    post = Post.query.get_or_404(post_id)
    return rt('post.html', title=post.title, post=post)


@app.route("/user/<string:username>/posts")
def posts_user(username):
    page = request.args.get('page', 1, type=int)
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).paginate(page=page, per_page=5)
    return rt('posts_user.html', posts=posts, user=user)


@app.route("/post/<int:post_id>/update", methods=['GET', 'POST'])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        flash('Your post has been edited!', 'success')
        return redirect(url_for('post', post_id=post.id))
    elif request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content
    return rt('create_post.html', title='Update Post', form=form, legend='Update Post')


@app.route("/post/<int:post_id>/delete", methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!', 'success')
    return redirect(url_for('home'))


@app.route('/get')
def get_bot_response():
    user_text = request.args.get('msg')
    return str(response(user_text))

@app.route('/chart')
def chart():
    return render_template('chart.html')

@app.route('/jarvis')
def jarvis():
    return rt('jarvis.html', title=jarvis)


if __name__ == '__main__':
    app.run(debug=True)
