from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    settings = db.relationship('ShopSettings', backref='user', uselist=False, cascade="all, delete-orphan")

class ShopSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_name = db.Column(db.String(150), default='ICEBERG', server_default='ICEBERG')
    shop_name = db.Column(db.String(150), default='Sri Krishna Bakery', server_default='Sri Krishna Bakery')
    address = db.Column(db.String(300), default='Your Shop Address here...', server_default='Your Shop Address here...')
    mobile = db.Column(db.String(20), default='9876543210', server_default='9876543210')
    mobile2 = db.Column(db.String(20), default='', server_default='')
    qr_code_path = db.Column(db.String(255), default='', server_default='')

    def __init__(self, **kwargs):
        super(ShopSettings, self).__init__(**kwargs)
        if not self.company_name: self.company_name = 'ICEBERG'
        if not self.shop_name: self.shop_name = 'Sri Krishna Bakery'
        if not self.address: self.address = 'Your Shop Address here...'
        if not self.mobile: self.mobile = '9876543210'
        if not self.mobile2: self.mobile2 = ''
        if not self.qr_code_path: self.qr_code_path = ''

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(db.Float, default=0.0)
    category = db.Column(db.String(50)) # e.g., 'Main', 'Ice Cream'
    is_flavor = db.Column(db.Boolean, default=False) # For Ice Cream flavors

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(20), unique=True, nullable=False)
    date = db.Column(db.DateTime, default=get_ist_now)
    company_name = db.Column(db.String(150))
    shop_name = db.Column(db.String(150))
    location = db.Column(db.String(150))
    shop_address = db.Column(db.String(300))
    shop_mobile = db.Column(db.String(20))
    shop_mobile2 = db.Column(db.String(20))
    grand_total = db.Column(db.Float, nullable=False)
    advance_amount = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    balance_amount = db.Column(db.Float, default=0.0)
    pdf_path = db.Column(db.String(255))
    items = db.relationship('BillItem', backref='bill', lazy=True, cascade="all, delete-orphan")

class BillItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bill.id'), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
