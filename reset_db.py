from app import db, app
import os

def reset_database():
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    if os.path.exists(db_path):
        print(f"Deleting existing database file: {db_path}")
        os.remove(db_path)
    else:
        print("No existing database file found.")

    with app.app_context():
        print("Creating new database schema...")
        db.create_all()
        print("Database reset complete.")

if __name__ == '__main__':
    reset_database()
