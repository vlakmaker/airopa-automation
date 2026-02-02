"""
Database initialization script

Run this script to initialize the database and create all tables.

Usage:
    python -m airopa_automation.api.init_db
"""

from airopa_automation.api.models.database import init_db, drop_db, engine, Base
from sqlalchemy import inspect
import sys


def check_tables_exist():
    """Check if tables already exist in the database"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return len(tables) > 0


def main():
    """Main initialization function"""
    print("AIropa API - Database Initialization")
    print("=" * 50)

    # Check if tables already exist
    tables_exist = check_tables_exist()

    if tables_exist:
        print("\nWarning: Database tables already exist!")
        response = input("Do you want to drop existing tables and recreate? (yes/no): ")

        if response.lower() in ['yes', 'y']:
            print("\nDropping existing tables...")
            drop_db()
            print("Creating new tables...")
            init_db()
            print("\n✅ Database reinitialized successfully!")
        else:
            print("\nSkipping initialization. Existing tables preserved.")
            sys.exit(0)
    else:
        print("\nNo existing tables found. Creating database...")
        init_db()
        print("\n✅ Database initialized successfully!")

    # Show created tables
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\nCreated tables: {', '.join(tables)}")

    # Show table schemas
    print("\nTable Schemas:")
    print("-" * 50)
    for table in tables:
        print(f"\n{table}:")
        columns = inspector.get_columns(table)
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            print(f"  - {col['name']}: {col['type']} {nullable}")


if __name__ == "__main__":
    main()
