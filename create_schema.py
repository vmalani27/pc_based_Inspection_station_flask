import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
db = SQLAlchemy(app)

# Example schema: UserEntry, MeasuredHousing, MeasuredShaft
class UserEntry(db.Model):
    __tablename__ = 'user_entry'
    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    last_login = db.Column(db.DateTime)

class MeasuredHousing(db.Model):
    __tablename__ = 'measured_housings'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), nullable=False)
    roll_number = db.Column(db.String(50), nullable=False)
    housing_radius = db.Column(db.Float)
    timestamp = db.Column(db.DateTime)

class MeasuredShaft(db.Model):
    __tablename__ = 'measured_shafts'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), nullable=False)
    roll_number = db.Column(db.String(50), nullable=False)
    shaft_height = db.Column(db.Float)
    shaft_radius = db.Column(db.Float)
    timestamp = db.Column(db.DateTime)

if __name__ == '__main__':
    print('Creating all tables in the database...')
    with app.app_context():
        db.create_all()
    print('Database schema created successfully.')
