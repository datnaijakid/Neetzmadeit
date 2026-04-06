from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request, session, send_from_directory
import os
import smtplib
import ssl
from email.message import EmailMessage
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
import sqlite3
import json
import re
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'assets', 'img')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

ckeditor = CKEditor(app)
bootstrap = Bootstrap(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database helper functions
def get_db():
    db = sqlite3.connect('neetzmadeit.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with get_db() as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS product (
                id INTEGER PRIMARY KEY,
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
                id INTEGER PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL
            )
        ''')

        # Create an initial admin user if none exists. If the default
        # admin user is already present, update it to the new credentials.
        existing_user = db.execute('SELECT id, username FROM user LIMIT 1').fetchone()
        admin_username = os.environ.get('ADMIN_USERNAME', 'anita')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'pasnita0204')
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
        featured_products = db.execute('SELECT * FROM product WHERE is_featured = 1 ORDER BY created_at DESC').fetchall()
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
            'SELECT * FROM product WHERE is_featured = 1 AND id != ? ORDER BY created_at DESC LIMIT 4',
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

        sender = 'johnpaulpaschal2@gmail.com'
        password = 'wdvp jkim ccvm qarm'
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))

        msg = EmailMessage()
        msg['Subject'] = f'New contact form message from {name}'
        msg['To'] = 'neetzmade@gmail.com'
        msg['Reply-To'] = email

        sender = 'johnpaulpaschal2@gmail.com'
        password = 'wdvp jkim ccvm qarm'
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))

        msg = EmailMessage()
        msg['Subject'] = f'New contact form message from {name}'
        msg['To'] = 'neetzmade@gmail.com'
        msg['Reply-To'] = email
        if sender:
            msg['From'] = sender
        else:
            msg['From'] = email

        plain = f"You received a new message from the website contact form.\n\nName: {name}\nEmail: {email}\n\nMessage:\n{message}"
        html = f"""<html><body>
        <h2>New message from website</h2>
        <p><strong>Name:</strong> {name}<br>
        <strong>Email:</strong> {email}</p>
        <hr>
        <p>{message.replace('\n','<br>')}</p>
        </body></html>"""

        msg.set_content(plain)
        msg.add_alternative(html, subtype='html')

        if not (sender and password):
            flash("Email not sent. Server credentials not configured (set EMAIL_ADDRESS and EMAIL_PASSWORD).", "warning")
            return redirect(url_for('contact'))

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls(context=context)
                server.login(sender, password)
                server.send_message(msg)
            flash(f"Thank you {name} for your message! I'll be in touch with you shortly", "success")
        except Exception:
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

        if not name or not description:
            flash('Please fill out your name and describe your custom order.', 'danger')
            return redirect(url_for('custom_order'))

        if not (email or phone or instagram or tiktok or other):
            flash('Please provide at least one contact method.', 'danger')
            return redirect(url_for('custom_order'))

        sender = 'johnpaulpaschal2@gmail.com'
        password = 'wdvp jkim ccvm qarm'
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))

        msg = EmailMessage()
        msg['Subject'] = f'Custom Order Request from {name}'
        msg['To'] = 'neetzmade@gmail.com'
        if email:
            msg['Reply-To'] = email
        if sender:
            msg['From'] = sender

        contact_info = []
        if email:
            contact_info.append(f"<strong>Email:</strong> {email}")
        if phone:
            contact_info.append(f"<strong>Phone:</strong> {phone}")
        if instagram:
            contact_info.append(f"<strong>Instagram:</strong> {instagram}")
        if tiktok:
            contact_info.append(f"<strong>TikTok:</strong> {tiktok}")
        if other:
            contact_info.append(f"<strong>Other:</strong> {other}")

        contact_html = "<br>".join(contact_info)

        plain = f"""Custom Order Request from {name}

CUSTOM REQUEST:
{description}

CONTACT INFORMATION:
"""
        if email:
            plain += f"Email: {email}\n"
        if phone:
            plain += f"Phone: {phone}\n"
        if instagram:
            plain += f"Instagram: {instagram}\n"
        if tiktok:
            plain += f"TikTok: {tiktok}\n"
        if other:
            plain += f"Other: {other}\n"

        html = f"""<html><body>
        <h2>Custom Order Request from {name}</h2>
        <hr>
        <h3>Custom Request:</h3>
        <p>{description.replace(chr(10),'<br>')}</p>
        <hr>
        <h3>Contact Information:</h3>
        <p>{contact_html}</p>
        </body></html>"""

        msg.set_content(plain)
        msg.add_alternative(html, subtype='html')

        if not (sender and password):
            flash("Email not sent. Server credentials not configured.", "warning")
            return redirect(url_for('custom_order'))

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls(context=context)
                server.login(sender, password)
                server.send_message(msg)
            flash(f"Thank you {name}! Your custom order request has been sent. I'll be in touch soon!", "success")
        except Exception:
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

        sender = 'johnpaulpaschal2@gmail.com'
        password = 'wdvp jkim ccvm qarm'
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))

        msg = EmailMessage()
        msg['Subject'] = f'New Order from {name}'
        msg['To'] = 'neetzmade@gmail.com'
        if email:
            msg['Reply-To'] = email
        if sender:
            msg['From'] = sender

        contact_info = []
        if email:
            contact_info.append(f"<strong>Email:</strong> {email}")
        if phone:
            contact_info.append(f"<strong>Phone:</strong> {phone}")
        if instagram:
            contact_info.append(f"<strong>Instagram:</strong> {instagram}")
        if tiktok:
            contact_info.append(f"<strong>TikTok:</strong> {tiktok}")
        if other:
            contact_info.append(f"<strong>Other:</strong> {other}")

        contact_html = "<br>".join(contact_info)

        # Build items table
        items_html = """
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <thead>
                <tr style="border-bottom: 2px solid #ccc;">
                    <th style="text-align: left; padding: 10px;">Product</th>
                    <th style="text-align: right; padding: 10px;">Price</th>
                    <th style="text-align: center; padding: 10px;">Qty</th>
                    <th style="text-align: right; padding: 10px;">Subtotal</th>
                </tr>
            </thead>
            <tbody>
        """

        plain = f"""Order from {name}

ORDER ITEMS:
"""

        for item in cart_items:
            items_html += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 10px;">{item['name']}</td>
                    <td style="text-align: right; padding: 10px;">${item['price']:.2f}</td>
                    <td style="text-align: center; padding: 10px;">{item['quantity']}</td>
                    <td style="text-align: right; padding: 10px;">${item['subtotal']:.2f}</td>
                </tr>
            """
            plain += f"{item['name']} x {item['quantity']} @ ${item['price']:.2f} = ${item['subtotal']:.2f}\n"

        items_html += f"""
            </tbody>
            <tfoot>
                <tr style="border-top: 2px solid #ccc; font-weight: bold;">
                    <td style="padding: 10px;" colspan="3">Total:</td>
                    <td style="text-align: right; padding: 10px;">${total:.2f}</td>
                </tr>
            </tfoot>
        </table>
        """

        plain += f"\nOrder Total: ${total:.2f}\n\nCONTACT INFORMATION:\n"
        if email:
            plain += f"Email: {email}\n"
        if phone:
            plain += f"Phone: {phone}\n"
        if instagram:
            plain += f"Instagram: {instagram}\n"
        if tiktok:
            plain += f"TikTok: {tiktok}\n"
        if other:
            plain += f"Other: {other}\n"

        html = f"""<html><body>
        <h2>New Order from {name}</h2>
        <hr>
        <h3>Order Items:</h3>
        {items_html}
        <hr>
        <h3>Contact Information:</h3>
        <p>{contact_html}</p>
        </body></html>"""

        msg.set_content(plain)
        msg.add_alternative(html, subtype='html')

        if not (sender and password):
            flash("Email not sent. Server credentials not configured.", "warning")
            return redirect(url_for('checkout'))

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls(context=context)
                server.login(sender, password)
                server.send_message(msg)
            flash(f"Thank you {name}! Your order has been placed. I'll be in touch soon!", "success")
            session['cart'] = {}
            session.modified = True
            return redirect(url_for('home'))
        except Exception:
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
