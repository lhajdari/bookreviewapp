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

@app.route("/")
def index():
    if 'loggedin' in session:
        books = db.execute('SELECT * FROM books ORDER BY RANDOM() LIMIT 12').fetchall()
        if request.args.get('type'):
            if request.args.get('type') == 'author':
                books = db.execute('SELECT * FROM books where author = :author', {'author':request.args.get('name')})
            elif request.args.get('type') == 'date':
                books = db.execute('SELECT * FROM books where year = :year', {'year':request.args.get('name')})
        elif request.args.get('q'):
            books = db.execute('SELECT * FROM books where year LIKE :year or title LIKE :title or isbn LIKE :isbn or author LIKE :author',
                                {'year':request.args.get('q'), 'title': request.args.get('q'), 'isbn': request.args.get('q'), 'author': request.args.get('q')})
        return render_template('index.html.j2', username=session['username'], books=books)
    else:
        return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'loggedin' not in session:
        if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
            error = ''
            username = request.form.get('username')
            password = request.form.get('password')
            if username == '' and password == '':
                error = "Username and Password can not be empty"
            elif username == '' or password == '':
                error = "Username or Password can not be empty"
            else:
                user = db.execute('SELECT * FROM users WHERE username = :username AND password = :password', {"username": username, "password": password}).fetchone()
                if not user:
                    error = "Account does not exist"
                else:
                    session['loggedin'] = True
                    session['id'] = user['id']
                    session['username'] = user['username']
                    return redirect(url_for('index'))
                return render_template("rl.html.j2", error=error, method="login")
        return render_template("rl.html.j2", method="login")
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route("/register", methods=["GET", "POST"])
def register():
    if 'loggedin' not in session:
        error = ''
        if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
            username = request.form.get('username')
            password = request.form.get('password')
            if username == '' and password == '':
                error = "Username and Password can not be empty"
            elif username == '' or password == '':
                error = "Username or Password can not be empty"
            else:
                user = db.execute('SELECT * FROM users WHERE username = :username AND password = :password', {"username": username, "password": password}).fetchone()
                if not user:
                    db.execute("INSERT INTO users (username, password) VALUES (:username, :password)", {"username": username, "password": password})
                    db.commit()
                    user = db.execute('SELECT * FROM users WHERE username = :username AND password = :password', {"username": username, "password": password}).fetchone()
                    session['loggedin'] = True
                    session['id'] = user['id']
                    session['username'] = user['username']
                    return redirect(url_for('index'))
                else:
                    error = "Given username is already taken, please try with another username"
        return render_template("rl.html.j2", method="register", error=error)
    else:
        return redirect(url_for('index'))

@app.route("/api/goodreads/<string:isbn>", methods=["GET", "POST"])
def book(isbn):
    url = f"https://www.goodreads.com/search/index.xml?key=L6W3G2oCzxZaAfamSx7yXw&q={isbn}"
    res = requests.get(url)
    data = xmltodict.parse(res.text)
    book_details = {
        'isbn': isbn,
        'average_rating': data['GoodreadsResponse']['search']['results']['work']['average_rating'],
        'title': data['GoodreadsResponse']['search']['results']['work']['best_book']['title'],
        'author': data['GoodreadsResponse']['search']['results']['work']['best_book']['author']['name'],
        'image_url': data['GoodreadsResponse']['search']['results']['work']['best_book']['image_url'],
        'ratings_count': data['GoodreadsResponse']['search']['results']['work']['ratings_count']['#text']
    }
    reviews = db.execute("select users.username, reviews.description from books join reviews on books.id = reviews.book_id join users on reviews.user_id = users.id where books.isbn = :isbn", {"isbn": isbn}).fetchall()
    if request.method == 'POST' and request.form.get('description') is not '':
        description = request.form.get('description')
        user = session['id']
        # returns id as dict
        book = db.execute("SELECT id FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
        book_id = dict(book)
        db.execute("INSERT INTO reviews (description, user_id, book_id) VALUES (:description, :user_id, :book_id)", {"description":description, "user_id":user, "book_id":book_id['id']})
        db.commit()
        book = db.execute("SELECT id FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
        reviews = db.execute("select users.username, reviews.description from books join reviews on books.id = reviews.book_id join users on reviews.user_id = users.id where books.isbn = :isbn", {"isbn": isbn}).fetchall()
    return render_template('show.html.j2', book=book_details, reviews=reviews, username=session['username'])
