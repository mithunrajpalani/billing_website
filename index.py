import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, ShopSettings, Item, Bill, BillItem
from datetime import datetime, timedelta, timezone
import json
import base64
import mimetypes
from types import SimpleNamespace
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Determine if we are running on Vercel or similar read-only environment
IS_VERCEL = "VERCEL" in os.environ


def get_now():
    """Get current time in IST (UTC+5:30)"""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=5, minutes=30)

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
    
    # Clean problematic query parameters (like ?supa=... or others that psycopg2 dislikes)
    if "postgresql" in db_uri and "?" in db_uri:
        # Keep the base URI and strip parameters that often cause "invalid connection option"
        base_uri = db_uri.split("?")[0]
        # For Vercel/Supabase, usually no parameters are strictly needed by psycopg2 
        # unless it's sslmode, but default is often fine.
        db_uri = base_uri
        
    upload_folder = '/tmp/uploads'
    os.makedirs(upload_folder, exist_ok=True)
else:
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_uri = 'sqlite:///' + os.path.join(basedir, 'instance', 'billing.db')
    upload_folder = os.path.join(basedir, 'static', 'uploads')
    # Ensure folders exist
    os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
    os.makedirs(upload_folder, exist_ok=True)

# Supabase Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "billing")

# DEBUG: Print environment status (obfuscated)
print(f" * DEBUG: SUPABASE_URL: {SUPABASE_URL[:15] if SUPABASE_URL else 'None'}...")
print(f" * DEBUG: SUPABASE_KEY: {SUPABASE_KEY[:15] if SUPABASE_KEY else 'None'}...")
print(f" * DEBUG: SUPABASE_BUCKET: {SUPABASE_BUCKET}")

_supabase_client = None
def get_supabase():
    global _supabase_client
    if _supabase_client is None:
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
                print(f" * Supabase client initialized (Bucket: {SUPABASE_BUCKET})")
            except Exception as e:
                print(f" * Error initializing Supabase client: {e}")
    return _supabase_client

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

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    if supabase and (filename.startswith("qr_codes/") or "/" in filename):
        try:
            # Proxy from Supabase
            file_data = supabase.storage.from_(SUPABASE_BUCKET).download(filename)
            if file_data:
                mime_type, _ = mimetypes.guess_type(filename)
                response = make_response(file_data)
                response.headers['Content-Type'] = mime_type or 'image/png'
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response
        except Exception as e:
            print(f" * Proxy error for {filename}: {e}")
            
    # Fallback to local
    try:
        response = make_response(send_from_directory(app.config['UPLOAD_FOLDER'], filename))
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    except Exception as e:
        return f"File not found: {filename}", 404

_cached_settings = None
_cached_footer_base64 = None

@app.context_processor
def inject_settings():
    global _cached_settings
    db_uri_config = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_type = 'Persistent (PostgreSQL)' if 'postgresql' in db_uri_config else 'Persistent (Local SQLite)'
    
    if _cached_settings:
        return dict(settings=_cached_settings, db_type=db_type)
    
    try:
        settings_record = ShopSettings.query.first()
        if not settings_record:
            settings_record = ShopSettings()
            admin = User.query.filter_by(username='admin').first()
            if admin:
                settings_record.user_id = admin.id
                db.session.add(settings_record)
                db.session.commit()
        
        display_qr_path = getattr(settings_record, 'qr_code_path', '') or ''
        
        def get_display_settings(obj, qr_path):
            return {
                'shop_name': getattr(obj, 'shop_name', 'Sri Krishna Bakery') or 'Sri Krishna Bakery',
                'company_name': getattr(obj, 'company_name', 'ice Berg') or 'ice Berg',
                'address': getattr(obj, 'address', 'Your Shop Address here...') or 'Your Shop Address here...',
                'mobile': getattr(obj, 'mobile', '9876543210') or '9876543210',
                'mobile2': getattr(obj, 'mobile2', '') or '',
                'qr_code_path': qr_path
            }
            
        settings_data = get_display_settings(settings_record, display_qr_path)
        _cached_settings = SimpleNamespace(**settings_data)
        return dict(settings=_cached_settings, db_type=db_type)
    except Exception as e:
        print(f" * Error in inject_settings: {e}")
        fallback = SimpleNamespace(shop_name='Sri Krishna Bakery', company_name='ice Berg', address='Your Shop Address here...', mobile='9876543210', mobile2='', qr_code_path='')
        return dict(settings=fallback, db_type=db_type)

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except:
        return None

# Create database and seed initial data
def seed_data():
    with app.app_context():
        # Move create_all to the main block to avoid overhead in requests
        # Create default user if not exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print(" * Seeding: Creating default admin user...")
            hashed_password = generate_password_hash('admin123', method='pbkdf2:sha256')
            admin = User(username='admin', password=hashed_password)
            db.session.add(admin)
            db.session.commit()
        
        # Create default shop settings for admin if not exists
        settings_record = ShopSettings.query.first()
        if not settings_record:
            print(" * Seeding: Creating default shop settings...")
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
        
        return render_template('dashboard.html', 
                              items=items, 
                              flavors=ice_cream_flavors, 
                              fruit_items=fruit_items,
                              drink_items=drink_items,
                              beeda_items=beeda_items,
                              date=get_now())
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
        # No need to create separate settings for each user as we use global settings
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
    try:
        data = request.json
        bill_data = data.get('items', [])
        grand_total = float(data.get('grand_total', 0) or 0)
        advance_amount = float(data.get('advance_amount', 0) or 0)
        discount_amount = float(data.get('discount_amount', 0) or 0)
        balance_amount = float(data.get('balance_amount', grand_total - advance_amount - discount_amount) or 0)
        party_number = data.get('party_number', '')
        custom_location = data.get('location')
        bill_date_str = data.get('date')
        bill_time_str = data.get('time')
        
        bill_date = get_now()
        if bill_date_str:
            try:
                # Handle dd/mm/yyyy format
                bill_date = datetime.strptime(bill_date_str, '%d/%m/%Y')
                
                # If time is provided, use it, otherwise use current time
                if bill_time_str:
                    try:
                        time_parts = datetime.strptime(bill_time_str, '%H:%M')
                        bill_date = bill_date.replace(hour=time_parts.hour, minute=time_parts.minute, second=0)
                    except ValueError:
                        now = get_now()
                        bill_date = bill_date.replace(hour=now.hour, minute=now.minute, second=now.second)
                else:
                    now = get_now()
                    bill_date = bill_date.replace(hour=now.hour, minute=now.minute, second=now.second)
            except ValueError:
                try:
                    # Fallback to standard ISO format
                    bill_date = datetime.strptime(bill_date_str, '%Y-%m-%d')
                    if bill_time_str:
                        try:
                            time_parts = datetime.strptime(bill_time_str, '%H:%M')
                            bill_date = bill_date.replace(hour=time_parts.hour, minute=time_parts.minute, second=0)
                        except ValueError:
                            now = get_now()
                            bill_date = bill_date.replace(hour=now.hour, minute=now.minute, second=now.second)
                    else:
                        now = get_now()
                        bill_date = bill_date.replace(hour=now.hour, minute=now.minute, second=now.second)
                except ValueError:
                    pass

        # Use global settings
        settings_record = ShopSettings.query.first()
        if not settings_record:
            settings_record = ShopSettings()
            
        bill_number = f"BILL-{get_now().strftime('%Y%m%d%H%M%S')}"
        
        new_bill = Bill(
            bill_number=bill_number,
            date=bill_date,
            company_name=settings_record.company_name,
            shop_name=settings_record.shop_name,
            location=custom_location if custom_location else '',
            shop_address=settings_record.address,
            shop_mobile=settings_record.mobile,
            shop_mobile2=settings_record.mobile2,
            grand_total=grand_total,
            advance_amount=advance_amount,
            discount_amount=discount_amount,
            balance_amount=balance_amount,
            party_number=party_number,
            qr_code_path=settings_record.qr_code_path # SNAPSHOT: Save the QR code used for this bill
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
    except Exception as e:
        db.session.rollback()
        print(f" * ERROR in generate_bill: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'}), 500

@app.route('/migrate_db')
def migrate_db():
    from sqlalchemy import text
    try:
        columns_to_add = [
            ('party_number', 'VARCHAR(50)'),
            ('qr_code_path', 'VARCHAR(255)'),
            ('pdf_path', 'VARCHAR(255)')
        ]
        
        results = []
        for col_name, col_type in columns_to_add:
            try:
                # Direct attempt (Standard SQL / SQLite)
                db.session.execute(text(f'ALTER TABLE bill ADD COLUMN {col_name} {col_type}'))
                db.session.commit()
                results.append(f"Added {col_name}")
            except Exception as e:
                db.session.rollback()
                # If it fails, check if it's because it already exists
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    results.append(f"{col_name} already exists")
                else:
                    results.append(f"Failed to add {col_name}: {str(e)}")
        
        # 2. Data Migration: Update ICEBERG to ice Berg
        try:
            db.session.execute(text("UPDATE shop_settings SET company_name = 'ice Berg' WHERE company_name = 'ICEBERG'"))
            db.session.execute(text("UPDATE bill SET company_name = 'ice Berg' WHERE company_name = 'ICEBERG'"))
            db.session.commit()
            results.append("Updated 'ICEBERG' to 'ice Berg' in settings and bills")
        except Exception as e:
            db.session.rollback()
            results.append(f"Failed to update branding data: {str(e)}")
        
        return f"Migration results: <br> - " + "<br> - ".join(results)
    except Exception as e:
        return f"Migration failed check: {str(e)}"

@app.route('/view_bill/<bill_number>')
@login_required
def view_bill(bill_number):
    try:
        bill = Bill.query.filter_by(bill_number=bill_number).first_or_404()
        
        # NEW REQUIREMENT: Load fixed image from local folder 'static/images/bill_footer'
        global _cached_footer_base64
        
        if not _cached_footer_base64:
            footer_dir = os.path.join(app.root_path, 'static', 'images', 'bill_footer')
            if os.path.exists(footer_dir):
                image_files = [f for f in os.listdir(footer_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                if image_files:
                    footer_img_path = os.path.join(footer_dir, image_files[0])
                    try:
                        with open(footer_img_path, "rb") as img_file:
                            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
                            mime_type, _ = mimetypes.guess_type(footer_img_path)
                            _cached_footer_base64 = f"data:{mime_type or 'image/png'};base64,{encoded_string}"
                    except Exception as e:
                        print(f" * ERROR: Footer image loading failed: {e}")
        
        return render_template('bill_view.html', bill=bill, qr_code_base64=_cached_footer_base64 or "")
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
        # Use a single global settings record
        settings = ShopSettings.query.first()
        if not settings:
            print(" * settings route: No settings found, creating default...")
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
                db.session.refresh(settings) # Refresh to get latest state
                
                # Invalidate cache so changes reflect on next request
                global _cached_settings
                _cached_settings = None
                
                flash('Settings updated successfully')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating settings: {str(e)}')
            return redirect(url_for('settings'))
        
        categories = ['Main', 'Ice Cream', 'Fruits', 'Beeda', 'Welcome Drinks']
        return render_template('settings.html', settings=settings, items=items, categories=categories)
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
        # Mask password in URI for display
        uri_parts = app.config['SQLALCHEMY_DATABASE_URI'].split('@')
        masked_uri = uri_parts[-1] if len(uri_parts) > 1 else app.config['SQLALCHEMY_DATABASE_URI']
        return f"Database Connected successfully! <br>Target: {masked_uri} <br><br>You can now go back to <a href='/'>Login</a>"
    except Exception as e:
        return f"Database Connection Error: {str(e)} <br><br>Current URI (masked): {app.config['SQLALCHEMY_DATABASE_URI'].split('@')[-1] if '@' in app.config['SQLALCHEMY_DATABASE_URI'] else 'SQLite'}", 500

# Run initialization once
_initialized = False
@app.before_request
def safe_init():
    global _initialized
    if not _initialized:
        # Set to True immediately to prevent multiple concurrent requests from re-triggering
        _initialized = True
        try:
            seed_data()
        except Exception as e:
            print(f"Lazy initialization error: {e}")
            # If it failed, maybe we should try again later? 
            # For now, let's just log it.

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True, host='0.0.0.0', port=5000)
