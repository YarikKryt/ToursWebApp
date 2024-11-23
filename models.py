from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Country(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(2), nullable=False, unique=True)
    route_points = db.relationship('RoutePoint', backref='country', lazy=True)
    tours_starting = db.relationship('Tour', backref='start_country', lazy=True)

    def __repr__(self):
        return f'<Country {self.name}>'


class Tour(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    start_country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False)
    start_city = db.Column(db.String(100), nullable=False)
    meeting_point = db.Column(db.String(200), nullable=False, default='Поки невідомо')  # Конкретне місце зустрічі
    meeting_time = db.Column(db.Time, nullable=True)  # Час зустрічі
    has_meals = db.Column(db.Boolean, default=False)
    meals_per_day = db.Column(db.Integer, nullable=True)
    min_number_of_people = db.Column(db.Integer, nullable=False, default=1)
    max_number_of_people = db.Column(db.Integer, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    route_points = db.relationship('RoutePoint', backref='tour', lazy=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    image_path = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f'<Tour {self.title}>'


class RoutePoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tour_id = db.Column(db.Integer, db.ForeignKey('tour.id'), nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False)
    sequence_number = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    location_type = db.Column(db.String(50), nullable=False)
    is_final = db.Column(db.Boolean, default=False, nullable=False)
    transport_to_next = db.Column(db.String(50))
    stay_duration_hours = db.Column(db.Integer)
    description = db.Column(db.Text)

    def __repr__(self):
        return f'<RoutePoint {self.location} ({self.sequence_number})>'

from werkzeug.security import generate_password_hash, check_password_hash


class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def __repr__(self):
        return f'<Admin {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Функція для ініціалізації бази даних з дефолтним адміном
def init_db():
    # Перевіряємо, чи вже є запис адміністратора
    if not Admin.query.first():
        default_admin = Admin(username='root', password_hash=generate_password_hash('root'))
        db.session.add(default_admin)
        db.session.commit()