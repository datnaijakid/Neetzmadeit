import sys
import os

# Ensure the root directory is on the Python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from main import app as flask_app

class PrefixMiddleware:
    """
    Middleware to strip /api/index or /api prefix added by Vercel serverless rewrites.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path.startswith('/api/index'):
            environ['PATH_INFO'] = path[len('/api/index'):] or '/'
        elif path.startswith('/api'):
            environ['PATH_INFO'] = path[len('/api'):] or '/'
        return self.wsgi_app(environ, start_response)

# Wrap application so routes match seamlessly on Vercel
app = PrefixMiddleware(flask_app)
handler = app
