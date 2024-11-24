from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify
import os
from datetime import datetime
from models import db, Tour, Country, RoutePoint, init_db
import pycountry  # Бібліотека для отримання списку країн
from pytz import timezone
from werkzeug.utils import secure_filename
import logging
from werkzeug.security import check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired
from functools import wraps

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ToursWebApp.db'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}
app.secret_key = '1003bc1c3e94a62aa965c2d780d659da'
logging.basicConfig(level=logging.DEBUG)
db.init_app(app)  # Ініціалізація бази даних

# Перевірка типу файлу
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:  # Перевірка наявності 'admin' в сесії
            flash("Access denied. Admins only.", "danger")
            return redirect(url_for('admin_login'))  # Перенаправлення на сторінку логіну
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@app.route('/home')
def home():  # put application's code here
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/tours')
def tours():
    # Отримання параметрів фільтрації
    title = request.args.get('title', type=str)
    tour_type = request.args.get('type', type=str)
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    start_country_id = request.args.get('start_country_id', type=int)
    duration_min = request.args.get('duration_min', type=int)
    duration_max = request.args.get('duration_max', type=int)
    start_date = request.args.get('start_date', type=str)
    end_date = request.args.get('end_date', type=str)

    # Початковий запит
    query = Tour.query

    # Динамічне додавання фільтрів
    if title:
        query = query.filter(Tour.title.ilike(f"%{title}%"))
    if tour_type:
        query = query.filter(Tour.type == tour_type)
    if min_price is not None:
        query = query.filter(Tour.price >= min_price)
    if max_price is not None:
        query = query.filter(Tour.price <= max_price)
    if start_country_id:
        query = query.filter(Tour.start_country_id == start_country_id)
    if duration_min:
        query = query.filter(Tour.duration_days >= duration_min)
    if duration_max:
        query = query.filter(Tour.duration_days <= duration_max)
    if start_date:
        query = query.filter(Tour.start_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Tour.end_date <= datetime.strptime(end_date, '%Y-%m-%d').date())

    # Виконання запиту
    filtered_tours = query.order_by(Tour.created_at.desc()).all()

    # Передача фільтрів у шаблон
    countries = Country.query.all()  # Список країн для фільтрування
    return render_template('tours.html', AllTours=filtered_tours, countries=countries)


@app.route('/tours/<int:id>')
def tour_details(id):
    tour = Tour.query.get(id)
    return render_template('tour_details.html', tour=tour)

@app.route('/tours/<int:id>/delete')
def tour_delete(id):
    tour = Tour.query.get_or_404(id)

    try:
        db.session.delete(tour)
        db.session.commit()
        return redirect(url_for('tours'))

    except Exception as e:
        return render_template('error.html', error_message=str(e)), 500

@app.route('/tours/<int:id>/update', methods=['GET', 'POST'])
def tour_update(id):
    tour = Tour.query.get(id)
    countries = Country.query.all()

    if request.method == 'POST':
        # Отримуємо дані з форми
        tour.title = request.form['title']
        tour.type = request.form['type']
        tour.price = request.form['price']
        tour.start_country_id = request.form['start_country_id']
        tour.start_city = request.form['start_city']
        tour.meeting_point = request.form.get('meeting_point', 'Поки невідомо')
        tour.meeting_time = request.form.get('meeting_time', None)
        if tour.meeting_time:
            try:
                tour.meeting_time = datetime.strptime(
                    tour.meeting_time.split(':')[0] + ':' + tour.meeting_time.split(':')[1], '%H:%M').time()
            except ValueError:
                tour.meeting_time = None

        tour.has_meals = 'has_meals' in request.form
        tour.meals_per_day = request.form.get('meals_per_day')
        tour.min_number_of_people = request.form['min_number_of_people']
        tour.max_number_of_people = request.form['max_number_of_people']
        tour.duration_days = request.form['duration_days']
        tour.description = request.form.get('description', '')

        # Перетворення дат з рядка на об'єкт date
        tour.start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        tour.end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()

        # Перевірка, чи вибрали нове зображення
        if 'image' in request.files and request.files['image'].filename != '':
            image = request.files['image']
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image_path = os.path.join('img', 'tours', filename).replace('\\', '/')

                # Зберігаємо нове зображення
                image.save(os.path.join('static', image_path))  # Зберігаємо в папці static
                tour.image_path = image_path  # Оновлюємо шлях до зображення
        else:
            # Якщо нове зображення не завантажено, залишаємо поточне зображення
            pass

        try:
            db.session.commit()
            return redirect(url_for('tours'))  # Перехід на сторінку турів
        except Exception as e:
            return render_template('error.html', error_message=str(e)), 500
    else:
        return render_template('tour_update.html', tour=tour, countries=countries)


@app.route('/admin/tours/create-tour', methods=['GET', 'POST'])
@admin_required
def create_tour():
    if request.method == 'POST':
        # Отримуємо дані з форми
        title = request.form['title']
        type = request.form['type']
        price = request.form['price']
        start_country_id = request.form['start_country_id']
        start_city = request.form['start_city']
        meeting_point = request.form.get('meeting_point', 'Поки невідомо')
        meeting_time = request.form.get('meeting_time', None)
        if meeting_time:
            meeting_time = datetime.strptime(meeting_time, '%H:%M').time()
        has_meals = 'has_meals' in request.form
        meals_per_day = request.form.get('meals_per_day')
        min_number_of_people = request.form['min_number_of_people']
        max_number_of_people = request.form['max_number_of_people']
        duration_days = request.form['duration_days']
        description = request.form.get('description', '')
        start_date = request.form['start_date']
        end_date = request.form['end_date']

        # Завантаження зображення
        image_path = None
        if 'image' in request.files:
            image = request.files['image']
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                # Шлях до папки, де зберігатимуться зображення (без 'static\')
                image_path = os.path.join('img', 'tours', filename).replace('\\', '/')

                # Зберігаємо файл
                image.save(os.path.join('static', image_path))  # Зберігаємо в папці static

        # Створення нового туру
        kyiv_tz = timezone('Europe/Kyiv')
        new_tour = Tour(
            title=title,
            type=type,
            price=price,
            start_country_id=start_country_id,
            start_city=start_city,
            meeting_point=meeting_point,
            meeting_time=meeting_time,
            has_meals=has_meals,
            meals_per_day=meals_per_day,
            min_number_of_people=min_number_of_people,
            max_number_of_people=max_number_of_people,
            duration_days=duration_days,
            description=description,
            start_date=datetime.strptime(start_date, '%Y-%m-%d'),
            end_date=datetime.strptime(end_date, '%Y-%m-%d'),
            created_at=datetime.now(kyiv_tz),
            image_path=image_path  # Зберігаємо відносний шлях до зображення в БД
        )
        try:
            db.session.add(new_tour)
            db.session.commit()
            return redirect(url_for('admin_tours'))  # Перехід на головну сторінку або іншу
        except Exception as e:
            return render_template('error.html', error_message=str(e)), 500

    countries = Country.query.all()  # Завантаження всіх країн для випадаючого списку
    return render_template('create-tour.html', countries=countries)


@app.route('/tours/<int:id>/route-points/delete/<int:point_id>', methods=['POST'])
def delete_route_point(id, point_id):
    try:
        point = RoutePoint.query.get_or_404(point_id)
        if point.tour_id != id:
            abort(404)

        # Get all points after the deleted one
        subsequent_points = RoutePoint.query.filter(
            RoutePoint.tour_id == id,
            RoutePoint.sequence_number > point.sequence_number
        ).all()

        # Update sequence numbers
        for subsequent_point in subsequent_points:
            subsequent_point.sequence_number -= 1

        db.session.delete(point)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/admin/tours/<int:id>/route-points/update', methods=['GET', 'POST'])
def update_tour_route_points(id):
    tour = Tour.query.get_or_404(id)
    route_points = RoutePoint.query.filter_by(tour_id=id).order_by(RoutePoint.sequence_number).all()
    countries = Country.query.all()

    if request.method == 'POST':
        try:
            # Валідація існуючих точок
            # Вивід даних форми для налагодження
            print("Received form data:")
            for key, value in request.form.items():
                print(f"{key}: {value}")
            has_final_point = False
            final_point_sequence = 0
            validation_errors = []

            # Функція для валідації точки маршруту
            def validate_route_point(location, type_, country_id, sequence_num):
                errors = []
                if not location:
                    errors.append(f"Location for point {sequence_num} cannot be empty")
                if not type_:
                    errors.append(f"Type for point {sequence_num} cannot be empty")
                if not country_id:
                    errors.append(f"Country for point {sequence_num} must be selected")
                return errors

            # Перевірка існуючих точок
            for point in route_points:
                point_id = str(point.id)
                form_data = {
                    'location': request.form[f'route_point_{point_id}'].strip(),
                    'type': request.form[f'type_{point_id}'].strip(),
                    'country_id': request.form[f'country_{point_id}'],
                    'is_final': f'is_final_{point_id}' in request.form
                }

                validation_errors.extend(validate_route_point(
                    form_data['location'],
                    form_data['type'],
                    form_data['country_id'],
                    point.sequence_number
                ))

                if form_data['is_final']:
                    if has_final_point:
                        validation_errors.append("Multiple final points are not allowed")
                    has_final_point = True
                    final_point_sequence = point.sequence_number

            # Перевірка нових точок
            new_points_data = zip(
                request.form.getlist('new_location[]'),
                request.form.getlist('new_type[]'),
                request.form.getlist('new_country[]'),
                request.form.getlist('new_is_final[]')
            )

            current_sequence = len(route_points)
            for i, (location, type_, country_id, is_final) in enumerate(new_points_data, 1):
                if location.strip():
                    validation_errors.extend(validate_route_point(
                        location.strip(),
                        type_.strip(),
                        country_id,
                        current_sequence + i
                    ))

                    if is_final and has_final_point:
                        validation_errors.append("Multiple final points are not allowed")
                    elif is_final:
                        has_final_point = True

            if validation_errors:
                return render_template('update_route_points.html',
                                       tour=tour,
                                       route_points=route_points,
                                       countries=countries,
                                       errors=validation_errors)

            # Оновлення існуючих точок
            for point in route_points:
                point_id = str(point.id)
                form_data = {
                    'location': request.form[f'route_point_{point_id}'].strip(),
                    'type': request.form[f'type_{point_id}'].strip(),
                    'country_id': request.form[f'country_{point_id}'],
                    'is_final': f'is_final_{point_id}' in request.form,
                    'transport': request.form[f'transport_{point_id}'].strip(),
                    'duration': request.form[f'duration_{point_id}'].strip(),
                    'description': request.form[f'description_{point_id}'].strip()
                }

                point.location = form_data['location']
                point.location_type = form_data['type']
                point.country_id = int(form_data['country_id'])
                point.is_final = form_data['is_final']
                point.transport_to_next = form_data['transport'] or None
                point.stay_duration_hours = int(form_data['duration']) if form_data['duration'] else None
                point.description = form_data['description'] or None

            # Додавання нових точок
            new_locations = request.form.getlist('new_location[]')
            current_max_sequence = len(route_points)

            for i, location in enumerate(new_locations):
                if location.strip():
                    new_point = RoutePoint(
                        tour_id=id,
                        sequence_number=current_max_sequence + i + 1,
                        location=location.strip(),
                        location_type=request.form.getlist('new_type[]')[i].strip(),
                        country_id=int(request.form.getlist('new_country[]')[i]),
                        is_final='new_is_final[]' in request.form and str(i) in request.form.getlist('new_is_final[]'),
                        transport_to_next=request.form.getlist('new_transport[]')[i].strip() or None,
                        stay_duration_hours=int(request.form.getlist('new_duration[]')[i])
                        if request.form.getlist('new_duration[]')[i].strip() else None,
                        description=request.form.getlist('new_description[]')[i].strip() or None
                    )
                    db.session.add(new_point)

            db.session.commit()
            flash('Route points updated successfully!', 'success')
            return redirect(url_for('update_tour_route_points', id=id))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating route points: {str(e)}")
            return render_template('update_route_points.html',
                                   tour=tour,
                                   route_points=route_points,
                                   countries=countries,
                                   errors=[f"Error: {str(e)}"])

    return render_template('update_route_points.html',
                           tour=tour,
                           route_points=route_points,
                           countries=countries)


# Функція для додавання країн
def add_countries():
    for country in pycountry.countries:
        existing_country = Country.query.filter_by(code=country.alpha_2).first()
        if not existing_country:  # Якщо країна ще не існує
            new_country = Country(name=country.name, code=country.alpha_2)
            db.session.add(new_country)
    db.session.commit()

# Створення таблиць (тільки для розробки)
with app.app_context():
    db.create_all()
    init_db()
    add_countries()


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    form = LoginForm()
    error = None
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        # Логіка перевірки введених даних
        if username == 'root' and password == 'root':
            session['admin'] = True  # Зберігаємо, що користувач авторизований
            return redirect(url_for('admin_panel'))  # Перехід до адмін панелі
        else:
            error = 'Неправильний логін або пароль'

    return render_template('admin_login.html', form=form, error=error)

@app.route('/admin-panel')
def admin_panel():
    if 'admin' not in session:  # Перевірка, чи є інформація в сесії
        return redirect(url_for('admin_login'))  # Перенаправлення на сторінку входу
    return render_template('admin_panel.html')  # Ваша адмін панель


@app.route('/admin-logout')
def logout():
    session.pop('admin', None)  # Видалення інформації з сесії при виході
    return redirect(url_for('admin_login'))  # Перенаправлення на сторінку входу

@app.route('/admin/tours', methods=['GET'])
@admin_required
def admin_tours():
    page = request.args.get('page', 1, type=int)  # Пагінація
    tours = Tour.query.paginate(page=page, per_page=10)  # Показуємо по 10 турів на сторінку
    return render_template('admin_tours.html', tours=tours)

@app.route('/admin/tours/<int:id>', methods=['GET'])
@admin_required
def admin_tour_details(id):
    tour = Tour.query.get_or_404(id)
    route_points = RoutePoint.query.filter_by(tour_id=id).order_by(RoutePoint.sequence_number).all()
    return render_template('admin_tour_details.html', tour=tour, route_points=route_points)

@app.route('/admin/tours/<int:id>/delete', methods=['POST'])
@admin_required
def delete_tour(id):
    tour = Tour.query.get_or_404(id)
    try:
        db.session.delete(tour)
        db.session.commit()
        flash("Tour deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")
    return redirect(url_for('admin_tours'))

@app.route('/admin/tours/<int:id>/update', methods=['GET', 'POST'])
@admin_required
def update_tour(id):
    tour = Tour.query.get_or_404(id)
    countries = Country.query.all()
    if request.method == 'POST':
        tour.title = request.form['title']
        tour.description = request.form['description']
        tour.price = request.form['price']
        # Можна додати логіку оновлення зображень
        db.session.commit()
        flash("Tour updated successfully.", "success")
        return redirect(url_for('admin_tour_details', id=id))
    return render_template('tour_update.html', tour=tour, countries=countries)


if __name__ == '__main__':
    app.run(debug=True)