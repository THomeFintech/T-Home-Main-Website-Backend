import sys
import os

# Make sure Python can find the app module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from app import models

print("Dropping all tables...")
models.Base.metadata.drop_all(bind=engine)
print("✅ Tables dropped.")

print("Creating all tables...")
models.Base.metadata.create_all(bind=engine)
print("✅ Tables recreated with new columns.")