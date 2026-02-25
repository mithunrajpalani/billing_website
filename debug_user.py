import os
from index import app, db, User, generate_password_hash

def debug():
    with app.app_context():
        print("Checking users in database...")
        users = User.query.all()
        if not users:
            print("No users found! Seeding default admin user.")
            hashed_password = generate_password_hash('admin123', method='pbkdf2:sha256')
            admin = User(username='admin', password=hashed_password)
            db.session.add(admin)
            db.session.commit()
            print("Admin user created: username='admin', password='admin123'")
        else:
            for u in users:
                print(f"User found: {u.username}")
                if u.username == 'admin':
                    print("Resetting admin password to 'admin123' for recovery...")
                    u.password = generate_password_hash('admin123', method='pbkdf2:sha256')
                    db.session.commit()
                    print("Admin password reset successfully.")

if __name__ == '__main__':
    debug()
