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


@app.route("/api/books/<isbn>", methods=["GET", "POST"])
def goodreads_api(isbn):
    if request.method == 'GET':
        url = f"https://www.goodreads.com/search/index.xml?key=L6W3G2oCzxZaAfamSx7yXw&q={isbn}"
        res = requests.get(url)
        data = xmltodict.parse(res.text)
        bookinfo = {
                        'isbn': isbn,
                        'author_name': data['GoodreadsResponse']['search']['results']['work']['best_book']['author']['name'],
                        'book_title': data['GoodreadsResponse']['search']['results']['work']['best_book']['title'],
                        'book_img': data['GoodreadsResponse']['search']['results']['work']['best_book']['image_url'],
                        'ratings_count': data['GoodreadsResponse']['search']['results']['work']['ratings_count']['#text'],
                        'avg_rating': data['GoodreadsResponse']['search']['results']['work']['average_rating']
                    }
        reviews = db.execute("select users.username, reviews.description from books join reviews on books.id = reviews.book_id join users on reviews.user_id = users.id where books.isbn = :isbn", {"isbn": isbn}).fetchall()
        return render_template('book.html', data=bookinfo, reviews=reviews)
    elif request.method == 'POST':
        description = request.form.get('description')
        user = session['id']
        book = db.execute("SELECT id FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
        book_id = dict(book)
        db.execute("INSERT INTO reviews (description, user_id, book_id) VALUES (:description, :user_id, :book_id)", {"description":description, "user_id":user, "book_id":book_id['id']})
        db.commit()
        return redirect(url_for('goodreads_api', isbn=isbn))


@app.route("/search", methods=["GET"])
def search():
    if 'loggedin' in session and 'q' in request.args:
        q = request.args.get('q')
        data = db.execute('SELECT * FROM books WHERE isbn = :isbn OR title = :title OR author = :author OR year = :year', {"isbn": q, "title": q, "author": q, "year": q}).fetchall()
        if data:
            return render_template('search.html', books=data)
        return render_template('404.html', q=q)
    else:
        return redirect(url_for('login'))
