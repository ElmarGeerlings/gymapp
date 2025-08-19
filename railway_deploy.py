#!/usr/bin/env python
"""
Railway Deployment Helper Script
This script helps with Railway deployment and troubleshooting
"""

import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gainz.settings')

def check_environment():
    """Check if all required environment variables are set"""
    print("🔍 Checking environment variables...")

    required_vars = ['DATABASE_URL']
    optional_vars = ['SECRET_KEY', 'DEBUG', 'GEMINI_API_KEY']

    missing_required = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_required.append(var)

    if missing_required:
        print(f"❌ Missing required environment variables: {', '.join(missing_required)}")
        return False

    print("✅ All required environment variables are set")

    for var in optional_vars:
        if os.environ.get(var):
            print(f"✅ {var} is set")
        else:
            print(f"⚠️  {var} is not set (optional)")

    return True

def test_database_connection():
    """Test database connection"""
    print("\n🔍 Testing database connection...")

    try:
        django.setup()
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            print("✅ Database connection successful")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def run_migrations():
    """Run Django migrations"""
    print("\n🔄 Running migrations...")

    try:
        django.setup()
        from django.core.management import execute_from_command_line
        execute_from_command_line(['manage.py', 'migrate', '--noinput'])
        print("✅ Migrations completed successfully")
        return True
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

def collect_static():
    """Collect static files"""
    print("\n📁 Collecting static files...")

    try:
        django.setup()
        from django.core.management import execute_from_command_line
        execute_from_command_line(['manage.py', 'collectstatic', '--noinput'])
        print("✅ Static files collected successfully")
        return True
    except Exception as e:
        print(f"❌ Static collection failed: {e}")
        return False

def main():
    """Main deployment process"""
    print("🚀 Railway Deployment Helper")
    print("=" * 40)

    # Check environment
    if not check_environment():
        print("\n❌ Environment check failed. Please set required variables.")
        sys.exit(1)

    # Test database
    if not test_database_connection():
        print("\n❌ Database connection failed. Check your DATABASE_URL.")
        sys.exit(1)

    # Run migrations
    if not run_migrations():
        print("\n❌ Migration failed.")
        sys.exit(1)

    # Collect static
    if not collect_static():
        print("\n❌ Static collection failed.")
        sys.exit(1)

    print("\n🎉 All checks passed! Your app is ready to deploy.")
    print("💡 If you're still having issues, check the Railway logs for more details.")

if __name__ == '__main__':
    main()
