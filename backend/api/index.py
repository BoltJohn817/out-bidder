import sys
import os

# Ensure the backend root is on the Python path so that
# bare imports (config, extensions, models, …) resolve correctly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

app = create_app()
