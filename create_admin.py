from getpass import getpass

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.core.security import hash_password


def create_admin():
    db: Session = SessionLocal()

    try:
        print("\n=== ExamForge Admin Setup ===\n")

        full_name = input("Admin full name: ").strip()
        email = input("Admin email: ").strip().lower()
        password = getpass("Admin password: ")

        if not full_name:
            print("Error: Full name cannot be empty.")
            return

        if not email:
            print("Error: Email cannot be empty.")
            return

        if len(password) < 8:
            print("Error: Password must contain at least 8 characters.")
            return

        existing_user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        if existing_user:
            print(f"\nError: A user with {email} already exists.")
            print(f"Existing role: {existing_user.role}")
            return

        admin = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            role="ADMIN",
            status="ACTIVE",
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("\nAdmin account created successfully.")
        print(f"Name : {admin.full_name}")
        print(f"Email: {admin.email}")
        print(f"Role : {admin.role}")
        print(f"ID   : {admin.id}")

    except Exception as e:
        db.rollback()
        print(f"\nError creating admin: {e}")

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()