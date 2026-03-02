import os
from index import app, db, User, ShopSettings, Bill

def check_qr_records():
    with app.app_context():
        print("--- ShopSettings ---")
        settings = ShopSettings.query.all()
        for s in settings:
            user = User.query.get(s.user_id)
            print(f"User: {user.username if user else 'Unknown'} | QR Path: {s.qr_code_path}")
            if s.qr_code_path:
                full_path = os.path.join(app.config['UPLOAD_FOLDER'], s.qr_code_path)
                print(f"  File exists: {os.path.exists(full_path)} ({full_path})")

        print("\n--- Latest Bills ---")
        bills = Bill.query.order_by(Bill.date.desc()).limit(5).all()
        for b in bills:
            print(f"Bill Num: {b.bill_number} | QR Path: {b.qr_code_path}")
            if b.qr_code_path:
                full_path = os.path.join(app.config['UPLOAD_FOLDER'], b.qr_code_path)
                print(f"  File exists: {os.path.exists(full_path)} ({full_path})")

if __name__ == '__main__':
    check_qr_records()
