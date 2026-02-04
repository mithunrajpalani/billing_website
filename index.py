import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, ShopSettings, Item, Bill, BillItem
from datetime import datetime, timedelta
import json
from types import SimpleNamespace

# Determine if we are running on Vercel or similar read-only environment
IS_VERCEL = "VERCEL" in os.environ

if IS_VERCEL:
    # On Vercel, the only writable directory is /tmp
    app = Flask(__name__, instance_path='/tmp')
    # Try common Vercel/Supabase environment variables
    db_uri = os.environ.get('DATABASE_URL') or \
             os.environ.get('POSTGRES_URL') or \
             os.environ.get('POSTGRES_URL_NON_POOLING') or \
             'sqlite:////tmp/billing.db'
    
    if db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)
    upload_folder = '/tmp/uploads'
    os.makedirs(upload_folder, exist_ok=True)
else:
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_uri = 'sqlite:///' + os.path.join(basedir, 'instance', 'billing.db')
    upload_folder = os.path.join('static', 'uploads')
    # Ensure instance folder exists
    os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = upload_folder

# Log database type (obfuscate password if present)
db_log_uri = db_uri
if '@' in db_log_uri:
    db_log_uri = db_log_uri.split('@')[1]
print(f" * Using Database: {db_log_uri.split(':')[0]}...")
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=31)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.context_processor
def inject_settings():
    db_uri_config = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_type = 'Persistent' if 'postgresql' in db_uri_config else 'Temporary (SQLite)'
    try:
        settings_record = None
        if current_user.is_authenticated:
            try:
                settings_record = current_user.settings
            except Exception as e:
                print(f" * Error fetching current_user.settings: {e}")
        
        if not settings_record:
            try:
                settings_record = ShopSettings.query.first()
            except Exception as e:
                print(f" * Error fetching ShopSettings.query.first(): {e}")
            
        settings_obj = settings_record if settings_record else ShopSettings()
        
        # Ensure strings for display
        display_settings = {
            'shop_name': getattr(settings_obj, 'shop_name', 'Sri Krishna Bakery') or 'Sri Krishna Bakery',
            'company_name': getattr(settings_obj, 'company_name', 'ICEBERG') or 'ICEBERG',
            'address': getattr(settings_obj, 'address', 'Your Shop Address here...') or 'Your Shop Address here...',
            'mobile': getattr(settings_obj, 'mobile', '9876543210') or '9876543210',
            'mobile2': getattr(settings_obj, 'mobile2', '') or '',
            'qr_code_path': getattr(settings_obj, 'qr_code_path', '') or ''
        }
            
        return dict(settings=SimpleNamespace(**display_settings), db_type=db_type)
    except Exception as e:
        print(f" * Critical error in inject_settings: {e}")
        fallback = {
            'shop_name': 'Sri Krishna Bakery', 
            'company_name': 'ICEBERG',
            'address': 'Your Shop Address here...',
            'mobile': '9876543210',
            'mobile2': '',
            'qr_code_path': ''
        }
        return dict(settings=SimpleNamespace(**fallback), db_type=db_type)

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except:
        return None

# Create database and seed initial data
def seed_data():
    with app.app_context():
        db.create_all()
        
        # Create default user if not exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print(" * Seeding: Creating default admin user...")
            hashed_password = generate_password_hash('admin123', method='pbkdf2:sha256')
            admin = User(username='admin', password=hashed_password)
            db.session.add(admin)
            db.session.commit()
        
        # Create default shop settings for admin if not exists
        if not admin.settings:
            print(" * Seeding: Creating default admin settings...")
            settings = ShopSettings(user_id=admin.id)
            db.session.add(settings)
            db.session.commit()
            
        # Create initial items if table is empty
        if not Item.query.first():
            initial_items = [
                {'name': 'Ice Cream', 'price': 0, 'category': 'Main'},
                {'name': 'Vanilla', 'price': 30, 'category': 'Ice Cream', 'is_flavor': True},
                {'name': 'Strawberry', 'price': 35, 'category': 'Ice Cream', 'is_flavor': True},
                {'name': 'Butterscotch', 'price': 40, 'category': 'Ice Cream', 'is_flavor': True},
                {'name': 'Pista', 'price': 40, 'category': 'Ice Cream', 'is_flavor': True},
                {'name': 'American Nuts', 'price': 50, 'category': 'Ice Cream', 'is_flavor': True},
                {'name': 'Kulfi Nuts', 'price': 50, 'category': 'Ice Cream', 'is_flavor': True},
                {'name': 'Italian Delight', 'price': 55, 'category': 'Ice Cream', 'is_flavor': True},
                {'name': 'Kaju Katli', 'price': 60, 'category': 'Ice Cream', 'is_flavor': True},
                {'name': 'Gulkand', 'price': 45, 'category': 'Ice Cream', 'is_flavor': True},
                {'name': 'Cassata', 'price': 70, 'category': 'Ice Cream', 'is_flavor': True},
                {'name': 'Fruits', 'price': 0, 'category': 'Main'},
                {'name': 'Mixing Fruits', 'price': 40, 'category': 'Fruits', 'is_flavor': True},
                {'name': 'Separate Fruits', 'price': 50, 'category': 'Fruits', 'is_flavor': True},
                {'name': 'Beeda', 'price': 0, 'category': 'Main'},
                {'name': 'Sweet Beeda', 'price': 15, 'category': 'Beeda', 'is_flavor': True},
                {'name': 'Sada Beeda', 'price': 15, 'category': 'Beeda', 'is_flavor': True},
                {'name': 'Welcome Drinks', 'price': 0, 'category': 'Main'},
                {'name': 'Fruit Salad', 'price': 30, 'category': 'Welcome Drinks', 'is_flavor': True},
                {'name': 'Rose Milk', 'price': 30, 'category': 'Welcome Drinks', 'is_flavor': True},
                {'name': 'Watermelon Juice', 'price': 30, 'category': 'Welcome Drinks', 'is_flavor': True},
                {'name': 'Popcorn', 'price': 20, 'category': 'Main'},
                {'name': 'Cotton Candy', 'price': 20, 'category': 'Main'},
                {'name': 'Chocolate Fountain', 'price': 100, 'category': 'Main'},
                {'name': 'Milk', 'price': 28, 'category': 'Main'},
                {'name': 'Curd', 'price': 30, 'category': 'Main'},
                {'name': 'Paneer', 'price': 100, 'category': 'Main'},
                {'name': 'Starters', 'price': 0, 'category': 'Main'},
                {'name': 'Boy', 'price': 0, 'category': 'Main'},
                {'name': 'Auto', 'price': 0, 'category': 'Main'}
            ]
            for item_data in initial_items:
                item = Item(**item_data)
                db.session.add(item)
        
        db.session.commit()

        # Ensure specific items exist
        for item_name in ['Starters', 'Boy', 'Auto']:
            if not Item.query.filter_by(name=item_name).first():
                new_item = Item(name=item_name, price=0, category='Main')
                db.session.add(new_item)
        
        db.session.commit()

@app.route('/')
@login_required
def index():
    try:
        items = Item.query.filter_by(is_flavor=False).all()
        ice_cream_flavors = Item.query.filter_by(category='Ice Cream', is_flavor=True).all()
        fruit_items = Item.query.filter_by(category='Fruits', is_flavor=True).all()
        drink_items = Item.query.filter_by(category='Welcome Drinks', is_flavor=True).all()
        beeda_items = Item.query.filter_by(category='Beeda', is_flavor=True).all()
        
        settings_record = current_user.settings or ShopSettings()
        # Create a display object for consistency
        settings_display = SimpleNamespace(
            shop_name=settings_record.shop_name or 'Sri Krishna Bakery',
            company_name=settings_record.company_name or 'ICEBERG',
            address=settings_record.address or 'Your Shop Address here...',
            mobile=settings_record.mobile or '9876543210',
            mobile2=settings_record.mobile2 or '',
            qr_code_path=settings_record.qr_code_path or ''
        )
        
        return render_template('dashboard.html', 
                              items=items, 
                              flavors=ice_cream_flavors, 
                              fruit_items=fruit_items,
                              drink_items=drink_items,
                              beeda_items=beeda_items,
                              settings=settings_display, 
                              date=datetime.now())
    except Exception as e:
        print(f" * Error in index route: {e}")
        return "Database is still initializing or connection failed. Please refresh in a few seconds.", 503

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                login_user(user, remember=True)
                session.permanent = True
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password')
        return render_template('login.html')
    except Exception as e:
        print(f" * Error in login route: {e}")
        # If DB isn't ready, at least show the page
        if request.method == 'POST':
            flash('Database connection error. Please try again in 1 minute.')
        return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('signup.html')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists')
            return render_template('signup.html')

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        # Create default settings for new user
        new_settings = ShopSettings(user_id=new_user.id)
        db.session.add(new_settings)
        db.session.commit()

        flash('Account created successfully! Please login.')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/generate_bill', methods=['POST'])
@login_required
def generate_bill():
    data = request.json
    bill_data = data.get('items', [])
    grand_total = float(data.get('grand_total', 0) or 0)
    advance_amount = float(data.get('advance_amount', 0) or 0)
    discount_amount = float(data.get('discount_amount', 0) or 0)
    balance_amount = float(data.get('balance_amount', grand_total - advance_amount - discount_amount) or 0)
    custom_location = data.get('location')
    bill_date_str = data.get('date')
    
    bill_date = datetime.now()
    if bill_date_str:
        try:
            # Handle dd/mm/yyyy format
            bill_date = datetime.strptime(bill_date_str, '%d/%m/%Y')
            # Add current time to the selected date
            now = datetime.now()
            bill_date = bill_date.replace(hour=now.hour, minute=now.minute, second=now.second)
        except ValueError:
            try:
                # Fallback to standard ISO format
                bill_date = datetime.strptime(bill_date_str, '%Y-%m-%d')
                now = datetime.now()
                bill_date = bill_date.replace(hour=now.hour, minute=now.minute, second=now.second)
            except ValueError:
                pass

    settings = current_user.settings or ShopSettings()
    bill_number = f"BILL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    new_bill = Bill(
        bill_number=bill_number,
        date=bill_date,
        company_name=settings.company_name,
        shop_name=settings.shop_name,
        location=custom_location if custom_location else '',
        shop_address=settings.address,
        shop_mobile=settings.mobile,
        shop_mobile2=settings.mobile2,
        grand_total=grand_total,
        advance_amount=advance_amount,
        discount_amount=discount_amount,
        balance_amount=balance_amount
    )
    db.session.add(new_bill)
    db.session.flush() # Get the bill id
    
    for item in bill_data:
        bill_item = BillItem(
            bill_id=new_bill.id,
            item_name=item['name'],
            quantity=item['quantity'],
            unit_price=item['price'],
            total_price=item['total']
        )
        db.session.add(bill_item)
    
    # Save session to get IDs for PDF generation
    db.session.commit()
    
    return jsonify({'status': 'success', 'bill_number': bill_number, 'view_url': url_for('view_bill', bill_number=bill_number)})

@app.route('/view_bill/<bill_number>')
@login_required
def view_bill(bill_number):
    try:
        bill = Bill.query.filter_by(bill_number=bill_number).first_or_404()
        # Use current settings as fallback for UI elements not in the bill record
        settings_record = current_user.settings or ShopSettings()
        settings_display = SimpleNamespace(
            shop_name=settings_record.shop_name or 'Sri Krishna Bakery',
            company_name=settings_record.company_name or 'ICEBERG',
            address=settings_record.address or 'Your Shop Address here...',
            mobile=settings_record.mobile or '9876543210',
            mobile2=settings_record.mobile2 or '',
            qr_code_path=settings_record.qr_code_path or ''
        )
        return render_template('bill_view.html', bill=bill, settings=settings_display)
    except Exception as e:
        print(f" * Error in view_bill route: {e}")
        return redirect(url_for('index'))

@app.route('/history')
@login_required
def history():
    try:
        bills = Bill.query.order_by(Bill.date.desc()).all()
        return render_template('history.html', bills=bills)
    except Exception as e:
        print(f" * Error in history route: {e}")
        return redirect(url_for('index'))

@app.route('/clear_history', methods=['POST'])
@login_required
def clear_history():
    try:
        # Delete all bill items first due to foreign key constraints if any (though cascade="all, delete-orphan" handles it)
        db.session.query(BillItem).delete()
        db.session.query(Bill).delete()
        db.session.commit()
        flash('Bill history cleared successfully')
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing history: {str(e)}')
    return redirect(url_for('history'))

@app.route('/delete_bill/<int:bill_id>', methods=['POST'])
@login_required
def delete_bill(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    try:
        db.session.delete(bill)
        db.session.commit()
        flash('Bill deleted successfully')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting bill: {str(e)}')
    return redirect(url_for('history'))

@app.route('/delete_item/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    item_name = item.name
    try:
        db.session.delete(item)
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'status': 'success', 'message': f'Item "{item_name}" deleted successfully'})
        flash(f'Item "{item_name}" deleted successfully')
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'status': 'error', 'message': f'Error deleting item: {str(e)}'}), 500
        flash(f'Error deleting item: {str(e)}')
    return redirect(url_for('settings'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    try:
        settings = current_user.settings
        if not settings:
            settings = ShopSettings(user_id=current_user.id)
            db.session.add(settings)
            db.session.commit()
        
        items = Item.query.all()
        if request.method == 'POST':
            settings.company_name = request.form.get('company_name')
            settings.shop_name = request.form.get('shop_name')
            settings.address = request.form.get('address')
            settings.mobile = request.form.get('mobile')
            settings.mobile2 = request.form.get('mobile2')
            
            # Handle QR Code Upload
            if 'qr_code' in request.files:
                file = request.files['qr_code']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Add timestamp to filename to avoid cache issues
                    filename = f"{int(datetime.now().timestamp())}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    settings.qr_code_path = filename
            
            # Add new item if provided
            new_item_name = request.form.get('new_item_name')
            new_item_price = request.form.get('new_item_price')
            new_item_category = request.form.get('new_item_category', 'Main')
            is_sub_item = request.form.get('is_sub_item') == 'on'

            if new_item_name and new_item_price:
                existing_item = Item.query.filter_by(name=new_item_name).first()
                if not existing_item:
                    new_item = Item(
                        name=new_item_name, 
                        price=float(new_item_price), 
                        category=new_item_category,
                        is_flavor=is_sub_item
                    )
                    db.session.add(new_item)
                else:
                    flash(f'Item "{new_item_name}" already exists.')
            
            # Update prices
            for item in items:
                new_price = request.form.get(f'price_{item.id}')
                if new_price:
                    item.price = float(new_price)
            
            # Account Management
            new_username = request.form.get('new_username')
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            
            if (new_username and new_username != current_user.username) or new_password:
                if not current_password or not check_password_hash(current_user.password, current_password):
                    flash('Current password is required and must be correct to change credentials.')
                    return redirect(url_for('settings'))
                
                if new_username:
                    existing_user = User.query.filter(User.username == new_username, User.id != current_user.id).first()
                    if existing_user:
                        flash(f'Username "{new_username}" is already taken.')
                    else:
                        current_user.username = new_username
                
                if new_password:
                    current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
                
                flash('Login credentials updated successfully.')
            
            try:
                db.session.commit()
                flash('Settings updated successfully')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating settings: {str(e)}')
            return redirect(url_for('settings'))
        
        return render_template('settings.html', settings=settings, items=items)
    except Exception as e:
        print(f" * Error in settings route: {e}")
        return redirect(url_for('index'))

@app.errorhandler(500)
def handle_500(e):
    # Try to extract the original exception if possible
    orig_msg = str(getattr(e, 'original_exception', e))
    print(f" * CRITICAL 500 ERROR: {orig_msg}")
    return f"Internal Server Error: {orig_msg}. <br><br>Visit /db-test for details.", 500

@app.route('/db-test')
def db_test():
    try:
        db.session.execute(db.text('SELECT 1'))
        return f"Database Connection Header: {app.config['SQLALCHEMY_DATABASE_URI'].split(':')[0]}... OK"
    except Exception as e:
        return f"Database Connection Error: {str(e)}", 500

# Run initialization once
_initialized = False
@app.before_request
def safe_init():
    global _initialized
    if not _initialized:
        try:
            seed_data()
            _initialized = True
        except Exception as e:
            print(f"Lazy initialization error: {e}")

if __name__ == '__main__':
    with app.app_context():
        seed_data()
    app.run(debug=True, host='0.0.0.0', port=5000)
