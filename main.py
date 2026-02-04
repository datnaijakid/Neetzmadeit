from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
import os
import smtplib
import ssl
from email.message import EmailMessage
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key'
ckeditor = CKEditor(app)
bootstrap = Bootstrap(app)

@app.route('/')
def home():
    return render_template('index.html')

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






if __name__ == "__main__":
    app.run(debug=True)