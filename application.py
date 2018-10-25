import os

from flask import Flask, session, render_template, request, url_for, flash, redirect, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import requests

from helpers import login_required

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


@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":
        search = request.form.get("search")
        searchquery = db.execute("SELECT * FROM books WHERE isbn = :search OR author ILIKE :q \
                                OR title ILIKE :q", {"search":search, "q":'%'+search+'%'}).fetchall()
        if not searchquery:
            return render_template("error.html", error="No results")
        secrets = "Secret unlocked! Here are your Search Results: "
        return render_template("search.html", searchquery=searchquery, secrets=secrets)
    else:
        return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Creates a user account"""

    if request.method == "POST":
        
        if not request.form.get("username"):
            return render_template("error.html", error="no username")
        

        # Ensure password was submitted
        elif not request.form.get("password") or not request.form.get("confirmation"):
            return render_template("error.html", error="no passwords submitted")

        # Ensure passwords match and meet length requirement
        elif not request.form.get("password") == request.form.get("confirmation") or len(request.form.get("password")) < 8:
            return render_template("error.html", error="passwords don't match, or too short")

        
        # Insert the username and password into the user table
        result = db.execute("INSERT INTO users (username, password) VALUES (:username, :password)",
                            {"username": request.form.get("username"), "password": request.form.get("password")})
        db.commit()

        if result is None:
            return render_template("error.html", error="DB not executed")
        
        # store their id in session to log them in automatically
        user_id = db.execute("SELECT id, username FROM users WHERE username = :username",
                            {"username": request.form.get("username")}).fetchone()
        session["user_id"] = user_id.id
        session["user_username"] = user_id.username

        flash("It Looks like everything works!")
        return render_template("index.html")

    else:
        return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Logs the user in"""
    
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        session.clear()

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("error.html", error="no username submitted")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("error.html", error="no password submitted")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          {"username": request.form.get("username")}).fetchone()

        if rows:
            print(f"{rows.username} and {rows.password} and {rows.id}")
        else:
            return render_template("error.html", error="no rows....")
        # Ensure username exists and password is correct
        if not rows.password == request.form.get("password"):
            return render_template("error.html", error="username or password incorrect")

        # Remember which user has logged in
        session["user_id"] = rows.id
        session["user_username"] = rows.username

        # Redirect user to home page
        return render_template("index.html")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Logs the user out and returns them to the login page"""
    
    session.clear()
    
    return render_template("login.html")


@app.route("/error")
def error():
    return render_template("error.html")

@app.route("/library")
@login_required
def list():
    books = db.execute("SELECT * FROM books").fetchall()
    return render_template("library.html", books=books)

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    if request.method == "POST":
        search = request.form.get("search")
        titlesearch = search.title()
        searchquery = db.execute("SELECT * FROM books WHERE isbn = :search OR author LIKE :q OR author LIKE :upper \
                                    OR title ILIKE :q", {"search":search, "q":'%'+search+'%', "upper":'%'+titlesearch+'%'}).fetchall()
        if not searchquery:
            return render_template("error.html", error="No results")
        secrets = "Secret unlocked! Here are your Search Results: "
        return render_template("search.html", searchquery=searchquery, secrets=secrets)
    else:
        print(session['user_id'])
        return render_template("search.html")

@app.route("/book", methods=["GET", "POST"])
@login_required
def book():
    if request.method == "POST":
        return render_template("book.html")
    else:
        return render_template("book.html")

@app.route("/book/<string:book_id>", methods=["GET", "POST"])
@login_required
def bookid(book_id):
    """Lists details about a single book."""
    
    # Load book info and reviews currently in db
    if request.method == "GET":
        book = db.execute("SELECT * FROM books where isbn = :isbn", {"isbn":book_id}).fetchone()
        if book is None:
            return render_template("error.html", error="No Book Found")
        review = db.execute("SELECT * FROM reviews WHERE isbn = :isbn", {"isbn":book_id}).fetchall()

        # Get JSON data about book
        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "9XTTdRjUwgZnXQ4gluBzA", "isbns": book_id})
        if res.status_code != 200:
            raise Exception("ERROR: API request unsuccessful.")
        book_data = res.json()

        return render_template("book.html", book=book, review=review, book_data=book_data['books'][0])

    else:
        prev_review = db.execute("SELECT * FROM reviews WHERE id=:id AND isbn=:isbn", {"isbn": book_id, "id": str(session['user_id'])}).fetchall()
        if prev_review:
            return render_template("error.html", error="Review Already Submitted")
        
        # Insert the id, rating, review, id, and ISBN into the user table
        result = db.execute("INSERT INTO reviews (id, isbn, review, rating, username) VALUES (:id, :isbn, :review, :rating, :username)",
                            {"id": session["user_id"], "isbn": book_id, "review": request.form.get("review"), "rating": request.form.get("rating"), "username":session['user_username']})
        db.commit()

        book = db.execute("SELECT * FROM books where isbn = :isbn", {"isbn":book_id}).fetchone()
        if book is None:
            return render_template("error.html", error="No Book Found")
        review = db.execute("SELECT * FROM reviews WHERE isbn = :isbn", {"isbn":book_id}).fetchall()

        # Get JSON data about book
        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "9XTTdRjUwgZnXQ4gluBzA", "isbns": book_id})
        if res.status_code != 200:
            raise Exception("ERROR: API request unsuccessful.")
        book_data = res.json()
        return render_template("book.html", book=book, review=review, book_data=book_data['books'][0])

@app.route("/api/<string:book_id>", methods=["GET"])
def book_api(book_id):
    """Return details about a single book"""
    
    book = db.execute("SELECT * FROM books where isbn = :isbn", {"isbn":book_id}).fetchone()
    if book is None:
        return render_template("error.html", error="No Book Found")
    
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "9XTTdRjUwgZnXQ4gluBzA", "isbns": book_id})
    if res.status_code != 200:
        raise Exception("ERROR: API request unsuccessful.")
    book_data = res.json()

    return jsonify({
            "title": book.title,
            "author": book.author,
            "year": book.year,
            "isbn": book_id,
            "review_count": book_data['books'][0]['work_ratings_count'],
            "average_score": book_data['books'][0]['average_rating']
        })