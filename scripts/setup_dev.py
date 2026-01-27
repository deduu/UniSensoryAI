import subprocess
import time
import sys
import os

def check_docker():
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def check_docker_compose():
    try:
        subprocess.run(["docker-compose", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Try docker compose (plugin)
        try:
            subprocess.run(["docker", "compose", "version"], check=True, capture_output=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

def main():
    print("🚀 Setting up development environment...")
    
    if not check_docker():
        print("❌ Docker not found. Please install Docker Desktop.")
        sys.exit(1)
        
    print("✅ Docker found.")
    
    # Start Docker Compose
    print("🐳 Starting PostgreSQL container...")
    try:
        subprocess.run(["docker-compose", "up", "-d"], check=True)
    except FileNotFoundError:
        try:
            subprocess.run(["docker", "compose", "up", "-d"], check=True)
        except Exception as e:
            print(f"❌ Failed to start docker-compose: {e}")
            sys.exit(1)
            
    # Wait for DB
    print("⏳ Waiting for database to be ready...")
    # Simple sleep for now, could actally poll the port or pg_isready
    time.sleep(5)
    
    # Run Migrations
    print("🔄 Running database migrations...")
    try:
        # Check if DATABASE_URL is set, if not result to default
        if "DATABASE_URL" not in os.environ:
            # Try loading from .env manually or default to 5433
             os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5433/unisensory"
            
        subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True)
        print("✅ Migrations applied successfully!")
    except subprocess.CalledProcessError:
        print("❌ Failed to apply migrations.")
        sys.exit(1)
        
    print("\n✨ Development environment ready!")
    print("Public DB URL: postgresql://postgres:postgres@localhost:5433/unisensory")

if __name__ == "__main__":
    main()
