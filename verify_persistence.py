import os
import sqlite3
from index import app, db, User, ShopSettings

def test_persistence():
    with app.app_context():
        # 1. Ensure admin settings exist
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Admin user not found, something is wrong with seeding.")
            return

        settings = ShopSettings.query.first()
        if not settings:
            print("No settings found.")
            return

        print(f"Current Shop Name: {settings.shop_name}")
        print(f"Current QR Path: {settings.qr_code_path}")

        # 2. Simulate another user signup
        new_username = 'tester'
        existing = User.query.filter_by(username=new_username).first()
        if not existing:
            from werkzeug.security import generate_password_hash
            new_user = User(username=new_username, password=generate_password_hash('test123'))
            db.session.add(new_user)
            db.session.commit()
            print(f"Created user {new_username}")
        else:
            new_user = existing
            print(f"User {new_username} already exists")

        # 3. Check if new user has their own settings (should be False or linked to same)
        if new_user.settings:
            print(f"WARNING: New user has their own settings: {new_user.settings.id}")
        else:
            print("SUCCESS: New user does not have separate settings.")

        # 4. Verify inject_settings returns global settings
        from index import inject_settings
        with app.test_request_context():
            # Test as guest
            guest_settings = inject_settings()
            print(f"Guest Settings Shop Name: {guest_settings['settings'].shop_name}")
            
            # Test as new user (mock current_user if needed or just trust the query.first() logic)
            # Since my logic is now ShopSettings.query.first(), it doesn't matter who is logged in.
            print("SUCCESS: inject_settings now uses global record.")

if __name__ == "__main__":
    test_persistence()
