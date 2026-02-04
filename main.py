from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
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











if __name__ == "__main__":
    app.run(debug=True)