from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request, session, send_from_directory
import os
import urllib.request
import urllib.parse
import urllib.error
import ssl
import shutil
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
import sqlite3
import json
import re
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import time
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
app.config['SECRET_KEY'] = b'\xee\xf8\xdb>\xf2\xda\xea,\x1e&\x10\xca\xa2\x0c\n3"-\x11&\'\xdf&\x0e'
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'assets', 'img')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

ckeditor = CKEditor(app)
bootstrap = Bootstrap(app)

# Ensure upload folder exists
try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except Exception:
    pass

@app.errorhandler(500)
def server_error(e):
    import traceback
    tb = traceback.format_exc()
    print("[FLASK 500 ERROR]", tb)
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Server Error - Neetzmadeit</title></head>
    <body style="font-family: monospace; padding: 2rem; background: #faf8f5; color: #333;">
        <h2>Neetzmadeit Server Diagnostic</h2>
        <p>A server error occurred. Details:</p>
        <pre style="background: #fff; border: 1px solid #ccc; padding: 1rem; border-radius: 6px; overflow-x: auto;">{tb}</pre>
    </body>
    </html>
    """, 500

# WSGI Middleware to handle Vercel Serverless rewrites seamlessly
class VercelWSGIMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path.startswith('/api/index.py'):
            environ['PATH_INFO'] = path[len('/api/index.py'):] or '/'
        elif path.startswith('/api/index'):
            environ['PATH_INFO'] = path[len('/api/index'):] or '/'
        elif path == '/api':
            environ['PATH_INFO'] = '/'
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelWSGIMiddleware(app.wsgi_app)

def send_web3forms(form_data):
    """
    Sends form data using the Web3Forms API (https://api.web3forms.com/submit).
    Requires WEB3FORMS_ACCESS_KEY in environment variables.
    """
    access_key = os.environ.get('WEB3FORMS_ACCESS_KEY', '').strip()
    if not access_key:
        print("[Web3Forms Warning] WEB3FORMS_ACCESS_KEY is not set in environment variables.")
        return False, "Form service is not configured. Please set WEB3FORMS_ACCESS_KEY."

    payload = {
        "access_key": access_key,
        "from_name": "Neetzmadeit Website",
        **form_data
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        "https://api.web3forms.com/submit",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Neetzmadeit-Flask-App"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            res_body = json.loads(response.read().decode('utf-8'))
            if res_body.get('success'):
                print(f"[Web3Forms Success] Form sent: {payload.get('subject', 'No Subject')}")
                return True, "Message sent successfully."
            else:
                msg = res_body.get('message', 'Unknown error')
                print(f"[Web3Forms Error] {msg}")
                return False, msg
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='ignore')
        print(f"[Web3Forms Error] HTTP {e.code}: {error_body}")
        return False, f"Web3Forms HTTP {e.code}: {error_body}"
    except Exception as e:
        print(f"[Web3Forms Error] Exception occurred: {e}")
        return False, str(e)

# Database helper functions & wrappers (Supports pg8000 for pure-Python Vercel/Lambda, psycopg2, and SQLite)
try:
    import pg8000.dbapi
except ImportError:
    pg8000 = None

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None

class PG8000CursorWrapper:
    def __init__(self, cur):
        self.cur = cur

    def fetchone(self):
        row = self.cur.fetchone()
        if row is None:
            return None
        if not self.cur.description:
            return row
        cols = [col[0] for col in self.cur.description]
        return dict(zip(cols, row))

    def fetchall(self):
        rows = self.cur.fetchall()
        if not rows:
            return []
        if not self.cur.description:
            return rows
        cols = [col[0] for col in self.cur.description]
        return [dict(zip(cols, row)) for row in rows]

class PG8000ConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn
        self.cur = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cur:
            try:
                self.cur.close()
            except Exception:
                pass
        if exc_type is not None:
            try:
                self.conn.rollback()
            except Exception:
                pass
        try:
            self.conn.close()
        except Exception:
            pass

    def execute(self, query, params=None):
        # Convert SQLite '?' placeholders to PostgreSQL '%s'
        pg_query = query.replace('?', '%s')
        # Quote table name "user" since it is a reserved word in PostgreSQL
        pg_query = re.sub(r'(?i)\bFROM user\b', 'FROM "user"', pg_query)
        pg_query = re.sub(r'(?i)\bINTO user\b', 'INTO "user"', pg_query)
        pg_query = re.sub(r'(?i)\bUPDATE user\b', 'UPDATE "user"', pg_query)

        # Convert SQLite boolean integer syntax (is_featured = 1 / 0) to Postgres boolean (is_featured = TRUE / FALSE)
        pg_query = re.sub(r'\bis_featured\s*=\s*1\b', 'is_featured = TRUE', pg_query, flags=re.IGNORECASE)
        pg_query = re.sub(r'\bis_featured\s*=\s*0\b', 'is_featured = FALSE', pg_query, flags=re.IGNORECASE)

        # Convert SQLite INSERT OR REPLACE for site_settings to PostgreSQL ON CONFLICT
        if "INSERT OR REPLACE INTO site_settings" in pg_query:
            pg_query = """
                INSERT INTO site_settings (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """

        self.cur = self.conn.cursor()
        if params:
            self.cur.execute(pg_query, params)
        else:
            self.cur.execute(pg_query)
        return PG8000CursorWrapper(self.cur)

    def commit(self):
        self.conn.commit()

class PostgresConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn
        self.cur = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cur:
            try:
                self.cur.close()
            except Exception:
                pass
        if exc_type is not None:
            try:
                self.conn.rollback()
            except Exception:
                pass
        try:
            self.conn.close()
        except Exception:
            pass

    def execute(self, query, params=None):
        # Convert SQLite '?' placeholders to PostgreSQL '%s'
        pg_query = query.replace('?', '%s')
        # Quote table name "user" since it is a reserved word in PostgreSQL
        pg_query = re.sub(r'(?i)\bFROM user\b', 'FROM "user"', pg_query)
        pg_query = re.sub(r'(?i)\bINTO user\b', 'INTO "user"', pg_query)
        pg_query = re.sub(r'(?i)\bUPDATE user\b', 'UPDATE "user"', pg_query)

        # Convert SQLite boolean integer syntax (is_featured = 1 / 0) to Postgres boolean (is_featured = TRUE / FALSE)
        pg_query = re.sub(r'\bis_featured\s*=\s*1\b', 'is_featured = TRUE', pg_query, flags=re.IGNORECASE)
        pg_query = re.sub(r'\bis_featured\s*=\s*0\b', 'is_featured = FALSE', pg_query, flags=re.IGNORECASE)

        # Convert SQLite INSERT OR REPLACE for site_settings to PostgreSQL ON CONFLICT
        if "INSERT OR REPLACE INTO site_settings" in pg_query:
            pg_query = """
                INSERT INTO site_settings (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """

        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        if params:
            self.cur.execute(pg_query, params)
        else:
            self.cur.execute(pg_query)
        return self.cur

    def commit(self):
        self.conn.commit()

class SQLiteConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            try:
                self.conn.rollback()
            except Exception:
                pass
        try:
            self.conn.close()
        except Exception:
            pass

    def execute(self, query, params=None):
        if params:
            return self.conn.execute(query, params)
        return self.conn.execute(query)

    def commit(self):
        self.conn.commit()

def get_db():
    database_url = os.environ.get('DATABASE_URL', '').strip()
    if database_url and (database_url.startswith('postgres://') or database_url.startswith('postgresql://')):
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)

        # First try pure-Python pg8000 (100% reliable on Vercel Serverless / AWS Lambda)
        if pg8000 is not None:
            try:
                url = urllib.parse.urlparse(database_url)
                ssl_context = ssl.create_default_context()
                conn = pg8000.dbapi.connect(
                    user=url.username,
                    password=url.password,
                    host=url.hostname,
                    port=url.port or 5432,
                    database=url.path.lstrip('/'),
                    ssl_context=ssl_context
                )
                return PG8000ConnectionWrapper(conn)
            except Exception as e:
                print(f"[pg8000 Warning] Connection failed: {e}. Trying psycopg2...")

        # Fallback to psycopg2
        if psycopg2 is not None:
            clean_url = database_url
            if 'channel_binding=' in clean_url:
                clean_url = re.sub(r'[?&]channel_binding=[^&]+', '', clean_url)
                if '?' not in clean_url and '&' in clean_url:
                    clean_url = clean_url.replace('&', '?', 1)
            conn = psycopg2.connect(clean_url)
            return PostgresConnectionWrapper(conn)

        raise RuntimeError("Neither pg8000 nor psycopg2 could connect to PostgreSQL.")

    # SQLite fallback (handles Vercel read-only filesystem safely)
    tmp_db = '/tmp/neetzmadeit.db'
    if (os.environ.get('VERCEL') or not os.access('.', os.W_OK)) and os.path.exists('neetzmadeit.db'):
        if not os.path.exists(tmp_db):
            try:
                shutil.copyfile('neetzmadeit.db', tmp_db)
            except Exception:
                pass
        db_path = tmp_db if os.path.exists(tmp_db) else 'neetzmadeit.db'
        conn = sqlite3.connect(db_path)
    else:
        conn = sqlite3.connect('neetzmadeit.db')

    conn.row_factory = sqlite3.Row
    return SQLiteConnectionWrapper(conn)

def init_db():
    try:
        database_url = os.environ.get('DATABASE_URL', '').strip()
        is_postgres = bool(database_url and (database_url.startswith('postgres://') or database_url.startswith('postgresql://')))

        with get_db() as db:
            if is_postgres:
                db.execute('''
                    CREATE TABLE IF NOT EXISTS "user" (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL
                    )
                ''')
                db.execute('''
                    CREATE TABLE IF NOT EXISTS product (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL,
                        price DOUBLE PRECISION NOT NULL,
                        images TEXT NOT NULL,
                        is_featured BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                db.execute('''
                    CREATE TABLE IF NOT EXISTS site_settings (
                        id SERIAL PRIMARY KEY,
                        key TEXT UNIQUE NOT NULL,
                        value TEXT NOT NULL
                    )
                ''')
            else:
                db.execute('''
                    CREATE TABLE IF NOT EXISTS user (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL
                    )
                ''')
                db.execute('''
                    CREATE TABLE IF NOT EXISTS product (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL,
                        price REAL NOT NULL,
                        images TEXT NOT NULL,
                        is_featured BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                db.execute('''
                    CREATE TABLE IF NOT EXISTS site_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT UNIQUE NOT NULL,
                        value TEXT NOT NULL
                    )
                ''')

            # Create initial admin user if none exists
            existing_user = db.execute('SELECT id, username FROM user LIMIT 1').fetchone()
            admin_username = 'anita'
            admin_password = 'pasnita0204'
            password_hash = generate_password_hash(admin_password)

            if not existing_user:
                db.execute(
                    'INSERT INTO user (username, password_hash) VALUES (?, ?)',
                    (admin_username, password_hash),
                )
                print(f'Created initial admin user: {admin_username}')
            elif existing_user['username'] == 'admin':
                db.execute(
                    'UPDATE user SET username = ?, password_hash = ? WHERE id = ?',
                    (admin_username, password_hash, existing_user['id']),
                )
                print(f'Updated default admin credentials to: {admin_username}')

            db.commit()
    except Exception as e:
        print(f"[init_db Warning] Could not initialize database on startup (will retry on first request): {e}")

# Initialize database
init_db()

# Helper functions
def get_cart():
    return session.get('cart', {})

def save_cart(cart):
    session['cart'] = cart
    session.modified = True

def cart_summary():
    cart = get_cart()
    items = []
    total = 0
    with get_db() as db:
        for product_id, quantity in cart.items():
            product = db.execute('SELECT * FROM product WHERE id = ?', (int(product_id),)).fetchone()
            if not product:
                continue
            subtotal = product['price'] * quantity
            total += subtotal
            images = json.loads(product['images']) if product['images'] else []
            main_image = images[0] if images else 'placeholder.jpg'
            items.append({
                'id': product['id'],
                'name': product['name'],
                'description': product['description'],
                'price': product['price'],
                'quantity': quantity,
                'subtotal': subtotal,
                'image': main_image,
            })
    return items, total

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def get_youtube_embed_url(url):
    """Convert YouTube URL to embed URL."""
    if not url:
        return None
    # Match various YouTube URL formats
    patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]+)',
        r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            return f'https://www.youtube.com/embed/{video_id}'
    return None

@app.template_filter('from_json')
def from_json_filter(value):
    try:
        return json.loads(value) if value else []
    except (TypeError, json.JSONDecodeError):
        return []

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper functions
def get_cart():
    return session.get('cart', {})

def save_cart(cart):
    session['cart'] = cart
    session.modified = True

def cart_summary():
    cart = get_cart()
    items = []
    total = 0
    with get_db() as db:
        for product_id, quantity in cart.items():
            product = db.execute('SELECT * FROM product WHERE id = ?', (int(product_id),)).fetchone()
            if not product:
                continue
            subtotal = product['price'] * quantity
            total += subtotal
            images = json.loads(product['images']) if product['images'] else []
            main_image = images[0] if images else 'placeholder.jpg'
            items.append({
                'id': product['id'],
                'name': product['name'],
                'description': product['description'],
                'price': product['price'],
                'quantity': quantity,
                'subtotal': subtotal,
                'image': main_image,
            })
    return items, total

# Routes
@app.route('/')
def home():
    with get_db() as db:
        featured_products = db.execute('SELECT * FROM product WHERE is_featured = TRUE ORDER BY created_at DESC').fetchall()
        youtube_setting = db.execute('SELECT value FROM site_settings WHERE key = ?', ('youtube_video',)).fetchone()
        youtube_channel = youtube_setting['value'] if youtube_setting else 'neetzmadeit'
        preview_setting = db.execute('SELECT value FROM site_settings WHERE key = ?', ('preview_video',)).fetchone()
        preview_video = preview_setting['value'] if preview_setting else ''
        youtube_embed = get_youtube_embed_url(preview_video) if preview_video else f'https://www.youtube.com/embed?listType=user_uploads&list={youtube_channel}'
    return render_template('index.html', featured_products=featured_products, youtube_channel=youtube_channel, youtube_embed=youtube_embed)

@app.route('/about')
def about():
    with get_db() as db:
        youtube_setting = db.execute('SELECT value FROM site_settings WHERE key = ?', ('youtube_video',)).fetchone()
        youtube_channel = youtube_setting['value'] if youtube_setting else 'neetzmadeit'
        preview_setting = db.execute('SELECT value FROM site_settings WHERE key = ?', ('preview_video',)).fetchone()
        preview_video = preview_setting['value'] if preview_setting else ''
        youtube_embed = get_youtube_embed_url(preview_video) if preview_video else f'https://www.youtube.com/embed?listType=user_uploads&list={youtube_channel}'
    return render_template('about.html', youtube_channel=youtube_channel, youtube_embed=youtube_embed)

@app.route('/shop')
def shop():
    with get_db() as db:
        products = db.execute('SELECT * FROM product ORDER BY created_at DESC').fetchall()
    return render_template('shop.html', products=products)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    with get_db() as db:
        product = db.execute('SELECT * FROM product WHERE id = ?', (product_id,)).fetchone()
        if not product:
            abort(404)
        images = json.loads(product['images']) if product['images'] else []
        related_products = db.execute(
            'SELECT * FROM product WHERE is_featured = TRUE AND id != ? ORDER BY created_at DESC LIMIT 4',
            (product_id,),
        ).fetchall()
    return render_template(
        'product_detail.html',
        product=product,
        images=images,
        all_products=related_products,
    )

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        if not (name and email and message):
            flash('Please fill out all fields.', 'danger')
            return redirect(url_for('contact'))

        form_data = {
            "subject": f"Contact Form Message from {name}",
            "Form Type": "Contact Form",
            "Name": name,
            "Email": email,
            "Message": message
        }

        success, err = send_web3forms(form_data)
        if success:
            flash(f"Thank you {name} for your message! I'll be in touch with you shortly.", "success")
        else:
            flash("There was an error sending your message. Please try again later.", "danger")
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/cart')
def cart():
    cart_items, total = cart_summary()
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/cart/add/<int:product_id>')
def add_to_cart(product_id):
    with get_db() as db:
        product = db.execute('SELECT * FROM product WHERE id = ?', (product_id,)).fetchone()
        if not product:
            abort(404)
    cart = get_cart()
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    save_cart(cart)
    flash(f"Added {product['name']} to your cart.", "success")
    return redirect(request.referrer or url_for('shop'))

@app.route('/cart/remove/<int:product_id>')
def remove_from_cart(product_id):
    cart = get_cart()
    with get_db() as db:
        product = db.execute('SELECT name FROM product WHERE id = ?', (product_id,)).fetchone()
    if str(product_id) in cart:
        cart.pop(str(product_id), None)
        save_cart(cart)
        if product:
            flash(f"Removed {product['name']} from your cart.", "warning")
    return redirect(url_for('cart'))

@app.route('/cart/update/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    quantity = int(request.form.get('quantity', 1))
    cart = get_cart()
    if quantity > 0:
        cart[str(product_id)] = quantity
    else:
        cart.pop(str(product_id), None)
    save_cart(cart)
    return redirect(url_for('cart'))

@app.route('/custom-order', methods=['GET', 'POST'])
def custom_order():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        instagram = request.form.get('instagram', '').strip()
        tiktok = request.form.get('tiktok', '').strip()
        other = request.form.get('other', '').strip()
        inspo_photo = request.files.get('inspo_photo')
        photo_name = None

        if not name or not description:
            flash('Please fill out your name and describe your custom order.', 'danger')
            return redirect(url_for('custom_order'))

        if not (email or phone or instagram or tiktok or other):
            flash('Please provide at least one contact method.', 'danger')
            return redirect(url_for('custom_order'))

        if inspo_photo and inspo_photo.filename:
            raw_photo_name = secure_filename(inspo_photo.filename)
            allowed_photo_extensions = {'png', 'jpg', 'jpeg', 'webp'}
            photo_extension = raw_photo_name.rsplit('.', 1)[-1].lower() if '.' in raw_photo_name else ''
            if not raw_photo_name or photo_extension not in allowed_photo_extensions:
                flash('Please upload a PNG, JPG, JPEG, or WEBP inspiration photo.', 'danger')
                return redirect(url_for('custom_order'))

            photo_data = inspo_photo.read()
            if len(photo_data) > 5 * 1024 * 1024:
                flash('Please choose an inspiration photo smaller than 5 MB.', 'danger')
                return redirect(url_for('custom_order'))

            # Save inspiration photo to custom_orders folder
            custom_orders_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_orders')
            os.makedirs(custom_orders_dir, exist_ok=True)
            photo_name = f"{int(time.time())}_{raw_photo_name}"
            with open(os.path.join(custom_orders_dir, photo_name), 'wb') as f:
                f.write(photo_data)

        form_data = {
            "subject": f"Custom Order Request from {name}",
            "Form Type": "Custom Order Request",
            "Customer Name": name,
            "Description": description,
            "Email": email or "Not provided",
            "Phone": phone or "Not provided",
            "Instagram": instagram or "Not provided",
            "TikTok": tiktok or "Not provided",
            "Other Contact": other or "Not provided",
            "Inspiration Photo": photo_name or "No photo uploaded"
        }

        success, err = send_web3forms(form_data)
        if success:
            flash(f"Thank you {name}! Your custom order request has been sent. I'll be in touch soon!", "success")
        else:
            flash("There was an error sending your request. Please try again later.", "danger")
        return redirect(url_for('custom_order'))
    return render_template('custom-order.html')

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart_items, total = cart_summary()

    if not cart_items:
        flash('Your cart is empty. Add items before checking out.', 'warning')
        return redirect(url_for('shop'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        instagram = request.form.get('instagram', '').strip()
        tiktok = request.form.get('tiktok', '').strip()
        other = request.form.get('other', '').strip()

        if not name:
            flash('Please provide your name.', 'danger')
            return redirect(url_for('checkout'))

        if not (email or phone or instagram or tiktok or other):
            flash('Please provide at least one contact method.', 'danger')
            return redirect(url_for('checkout'))

        order_items_text = "\n".join([
            f"• {item['name']} x {item['quantity']} @ ${item['price']:.2f} = ${item['subtotal']:.2f}"
            for item in cart_items
        ])

        form_data = {
            "subject": f"New Order from {name} - ${total:.2f}",
            "Form Type": "New Store Order",
            "Customer Name": name,
            "Email": email or "Not provided",
            "Phone": phone or "Not provided",
            "Instagram": instagram or "Not provided",
            "TikTok": tiktok or "Not provided",
            "Other Contact": other or "Not provided",
            "Order Items": order_items_text,
            "Total Amount": f"${total:.2f}"
        }

        success, err = send_web3forms(form_data)
        if success:
            flash(f"Thank you {name}! Your order has been placed. I'll be in touch soon!", "success")
            session['cart'] = {}
            session.modified = True
            return redirect(url_for('home'))
        else:
            flash("There was an error placing your order. Please try again later.", "danger")
            return redirect(url_for('checkout'))

    return render_template('checkout.html', cart_items=cart_items, total=total)

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        with get_db() as db:
            user = db.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()
            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                flash('Logged in successfully!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid username or password.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home'))

# Admin Routes
@app.route('/admin')
@login_required
def admin_dashboard():
    with get_db() as db:
        products = db.execute('SELECT * FROM product ORDER BY created_at DESC').fetchall()
    return render_template('admin/dashboard.html', products=products)

@app.route('/admin/products')
@login_required
def admin_products():
    with get_db() as db:
        products = db.execute('SELECT * FROM product ORDER BY created_at DESC').fetchall()
    return render_template('admin/products.html', products=products)

@app.route('/admin/products/add', methods=['GET', 'POST'])
@login_required
def admin_add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price', 0))
        is_featured = 'is_featured' in request.form

        # Handle file uploads
        images = []
        for i in range(1, 6):  # Allow up to 5 images
            file = request.files.get(f'image_{i}')
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Add timestamp to avoid conflicts
                filename = f"{int(time.time())}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                images.append(filename)

        if not images:
            images = ['placeholder.jpg']

        with get_db() as db:
            db.execute('''
                INSERT INTO product (name, description, price, images, is_featured)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, description, price, json.dumps(images), is_featured))
            db.commit()

        flash('Product added successfully!', 'success')
        return redirect(url_for('admin_products'))

    return render_template('admin/add_product.html')

@app.route('/admin/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_product(product_id):
    with get_db() as db:
        product = db.execute('SELECT * FROM product WHERE id = ?', (product_id,)).fetchone()
        if not product:
            abort(404)

    current_images = json.loads(product['images']) if product['images'] else []

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price', 0))
        is_featured = 'is_featured' in request.form

        # Handle new file uploads
        new_images = []
        for i in range(1, 6):
            file = request.files.get(f'image_{i}')
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filename = f"{int(time.time())}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                new_images.append(filename)

        # Keep existing images that weren't replaced
        for i, existing_image in enumerate(current_images):
            keep_key = f'keep_image_{i+1}'
            if request.form.get(keep_key) == 'on':
                new_images.append(existing_image)

        if not new_images:
            new_images = ['placeholder.jpg']

        with get_db() as db:
            db.execute('''
                UPDATE product SET name=?, description=?, price=?, images=?, is_featured=?
                WHERE id=?
            ''', (name, description, price, json.dumps(new_images), is_featured, product_id))
            db.commit()

        flash('Product updated successfully!', 'success')
        return redirect(url_for('admin_products'))

    return render_template('admin/edit_product.html', product=product, current_images=current_images)

@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
@login_required
def admin_delete_product(product_id):
    with get_db() as db:
        product = db.execute('SELECT images FROM product WHERE id = ?', (product_id,)).fetchone()
        if not product:
            abort(404)

        # Delete associated image files
        if product['images']:
            images = json.loads(product['images'])
            for image in images:
                if image != 'placeholder.jpg':
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], image))
                    except OSError:
                        pass  # File doesn't exist or can't be deleted

        db.execute('DELETE FROM product WHERE id = ?', (product_id,))
        db.commit()

    flash('Product deleted successfully!', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if request.method == 'POST':
        youtube_channel = request.form.get('youtube_channel')
        preview_video = request.form.get('preview_video')
        with get_db() as db:
            db.execute('''
                INSERT OR REPLACE INTO site_settings (key, value)
                VALUES (?, ?)
            ''', ('youtube_video', youtube_channel))
            db.execute('''
                INSERT OR REPLACE INTO site_settings (key, value)
                VALUES (?, ?)
            ''', ('preview_video', preview_video))
            db.commit()

        flash('Settings updated successfully!', 'success')
        return redirect(url_for('admin_settings'))

    with get_db() as db:
        youtube_setting = db.execute('SELECT value FROM site_settings WHERE key = ?', ('youtube_video',)).fetchone()
        youtube_channel = youtube_setting['value'] if youtube_setting else 'neetzmadeit'
        preview_setting = db.execute('SELECT value FROM site_settings WHERE key = ?', ('preview_video',)).fetchone()
        preview_video = preview_setting['value'] if preview_setting else ''
        preview_embed = get_youtube_embed_url(preview_video) if preview_video else None

    return render_template('admin/settings.html', youtube_channel=youtube_channel, preview_video=preview_video, preview_embed=preview_embed)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
