import os
import sys

# Set the application path
sys.path.insert(0, os.path.dirname(__file__))

# Set environment variables (optional)
os.environ['FLASK_APP'] = 'main.app'

# Import the application
from main import app as application
