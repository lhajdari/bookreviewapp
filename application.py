import os

from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import requests
import re

import json
import xmltodict

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/register", methods=["GET", "POST"])
def register():
    msg = ''
    if 'loggedin' in session:
        return redirect(url_for('index'))
    elif request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form.get('username')
        password = request.form.get('password')
        user = db.execute('SELECT * FROM users WHERE username = :username AND password = :password', {"username": username, "password": password}).fetchone()
        if user:
            msg = 'User already exists'
        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Username must contain only characters and numbers!'
        # elif not username or not password:
        #     msg = 'Please fill out the form!'
        else:
            db.execute("INSERT INTO users (username, password) VALUES (:username, :password)", {"username": username, "password": password})
            db.commit()
            msg = 'You\'ve successfully registered!'
    return render_template("register.html", msg=msg)


@app.route("/login", methods=['GET', 'POST'])
def login():
    msg = ''
    if 'loggedin' in session:
        return redirect(url_for('index'))

    elif request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form.get('username')
        password = request.form.get('password')
        user = db.execute('SELECT * FROM users WHERE username = :username AND password = :password', {"username": username, "password": password}).fetchone()
        if user:
            session['loggedin'] = True
            session['id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            msg = 'incorrect username/password'
    return render_template("index.html", msg=msg)


@app.route("/logout")
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route("/")
def index():
    if 'loggedin' in session:
        books = db.execute('SELECT * FROM books ORDER BY RANDOM() LIMIT 10').fetchall()
        return render_template('home.html', username=session['username'], books=books)
    return redirect(url_for('login'))


@app.route("/profile")
def profile():
    if 'loggedin' in session:
        user = db.execute("SELECT * FROM users WHERE id = :id", {"id": session['id']}).fetchone()
        return render_template('profile.html', user=user)
    else:
        return render_template(url_for('login'))


@app.route("/api/books/<isbn>")
def goodreads_api(isbn):
    url = f"https://www.goodreads.com/search/index.xml?key=L6W3G2oCzxZaAfamSx7yXw&q={isbn}"
    res = requests.get(url)
    data = xmltodict.parse(res.text)
    bookinfo = {
                    'author_name': data['GoodreadsResponse']['search']['results']['work']['best_book']['author']['name'],
                    'book_title': data['GoodreadsResponse']['search']['results']['work']['best_book']['title'],
                    'book_img': data['GoodreadsResponse']['search']['results']['work']['best_book']['image_url'],
                    'ratings_count': data['GoodreadsResponse']['search']['results']['work']['ratings_count']['#text'],
                    'avg_rating': data['GoodreadsResponse']['search']['results']['work']['average_rating']
                }
    return render_template('book.html', data=bookinfo)