import os
import json
import posixpath

from flask import Flask, render_template, session, request, flash, redirect
from flask_pymongo import PyMongo
from flask_qrcode import QRcode
from flask_bcrypt import Bcrypt
from flask_cors import CORS

app = Flask(__name__)
app.url_map.strict_slashes = False
QRcode(app)
flask_bcrypt = Bcrypt(app)
cors = CORS(app, resources={r"/api/*": {"origins": "*"}})

if not 'DYNO' in os.environ:
    with open("config.json") as configFile:
        jsonConfig = json.load(configFile)
        app.config["MONGO_URI"] = jsonConfig["MONGODB_CONNECTION_URL"]
        app.secret_key = jsonConfig["SECRET_KEY"]
        app.config["SALT"] = jsonConfig["SALT"]
else:
    app.config["MONGO_URI"] = os.environ["MONGODB_CONNECTION_URL"]
    app.secret_key = os.environ["SECRET_KEY"]

with open("events.json") as eventsFile:
    events = json.load(eventsFile)

with open("redeemables.json") as redeemablesFile:
    redeemables = json.load(redeemablesFile)

mongo = PyMongo(app)

@app.before_request
def before_request():
    if 'DYNO' in os.environ: # Only runs when on heroku
        if request.url.startswith('http://'):
            url = request.url.replace('http://', 'https://', 1)
            code = 301
            return redirect(url, code=code)

@app.route("/")
def home():
    if "logged_in" in session:
        points = mongo.db.users.find_one({"email": session["logged_in"]["email"]})["points"]
    else:
        points = "Not Logged In"
    return render_template("home.html", points = points)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if "logged_in" in session and session["logged_in"] != {}:
            flash("You are Already Logged In")
            return redirect("/")
        return render_template("login.html", points = "Not Logged In")
    elif request.method == "POST":
        email, password = request.form["email"], request.form["password"]
        if (found := mongo.db.users.find_one({"email": email})) is not None:
            if flask_bcrypt.check_password_hash(found["password"], password):
                session["logged_in"] = {"email": email, "admin": found["admin"]}
                flash("Successfully Logged In")
                return redirect("/")
            else:
                flash("Incorrect Password")
                return redirect("/login") 
        else:
            flash("Account with that email does not exist")
            return redirect("/login")

@app.route("/sign_up", methods=["GET", "POST"])
def sign_up():
    if request.method == "GET":
        if "logged_in" in session and  session["logged_in"] != {}:
            flash("You are Already Logged In")
            return redirect("/")
        return render_template("signup.html", points = "Not Logged In")
    elif request.method == "POST":
        email, password = request.form["email"], request.form["password"]
        if mongo.db.users.find_one({"email": email}) is None:
            mongo.db.users.insert_one({
                "email": email,
                "password": flask_bcrypt.generate_password_hash(password),
                "admin": False,
                "points": 0
            })
            session["logged_in"] = {"email": email}
            flash("Successfully Signed Up")
            return redirect("/")
        else:
            flash("An Account is Already Registered With That Email Address")
            return redirect("/")


@app.route("/logout")
def logout():
    if "logged_in" in session:
        del session["logged_in"]
        flash("Logged Out")
    else:
        flash("Not Logged In")
    return redirect("/")


@app.route("/events")
def show_events():
    if "logged_in" in session:
        points = mongo.db.users.find_one({"email": session["logged_in"]["email"]})["points"]
    else:
        points = "Not Logged In"
    return render_template("events.html", events = events, points = points)


@app.route("/redeemables")
def get_redeemables():
    if "logged_in" in session:
        points = mongo.db.users.find_one({"email": session["logged_in"]["email"]})["points"]
    else:
        points = "Not Logged In"
    return render_template("redeemables.html", points = points, redeemables = redeemables)


@app.route("/redeemable/<redeemable>", methods=["GET", "POST"])
def get_redeemable(redeemable):
    if request.method == "GET":
        if "logged_in" in session:
            points = mongo.db.users.find_one({"email": session["logged_in"]["email"]})["points"]
        else:
            points = "Not Logged In"
        return render_template("redeemable.html", points = points, redeemable = [
            redeemable, redeemables[redeemable]
        ])
    elif request.method == "POST":
        pass


@app.route("/admin_generate")
def admin_generate():
    if "logged_in" in session and  session["logged_in"] != {}:
        if session["logged_in"]["admin"] == True:
            events_with_qr = events
            if request.is_secure:
                connection_type = "https://"
            else:
                connection_type = "http://"
            for event_name in events:
                print(request.host)
                events_with_qr[event_name]["qrcode_url"] = posixpath.join(connection_type, request.host, f"eventParticipate/{event_name}")
            print(events_with_qr)
            return render_template("admin_generate.html", events = events_with_qr, points = "Not Logged In" if connection_type == "http://" else mongo.db.users.find_one({"email": session["logged_in"]["email"]})["points"])
        else:
            flash("Not Logged In As Admin")
            return redirect("/")
    else:
        flash("Not Logged In")
        return redirect("/")


@app.route("/eventParticipate/<eventName>")
def eventParticipate(eventName):
    if "logged_in" in session and session["logged_in"] != {}:
        points = mongo.db.users.find_one({"email": session["logged_in"]["email"]})["points"]
        mongo.db.users.update_one({"email": session["logged_in"]["email"]}, {"$set": {'points': points + events[eventName]["points"]}})
        flash(f"Thanks for participating in {eventName}! You earned {events[eventName]['points']}")
        return redirect("/")
    else:
        flash("Please Login to Get Points")
        return redirect("/")


@app.route("/api/get_user_points", methods=["POST"])
def get_user_points():
    return {
        "points": mongo.db.users.find_one({"email": request.json["email"]})["points"]
    }


@app.route("/api/login", methods=["POST"])
def api_login():
    email, password = request.json["email"], request.json["password"]
    if (found := mongo.db.users.find_one({"email": email})) is not None:
        if flask_bcrypt.check_password_hash(found["password"], password):
            session["logged_in"] = {"email": email, "admin": found["admin"]}
            return {"code": "Successfully Logged In"}
        else:
            return {"code": "Incorrect Password"}
    else:
        return {"code": "No Email with That Address Found"}


@app.route("/api/signup", methods=["POST"])
def api_signup():
    email, password = request.json["email"], request.json["password"]
    if mongo.db.users.find_one({"email": email}) is None:
        mongo.db.users.insert_one({
            "email": email,
            "password": flask_bcrypt.generate_password_hash(password),
            "admin": False,
            "points": 0
        })
        session["logged_in"] = {"email": email}
        return {"code": "Successfully Signed Up"}
    else:
        return {"code": "An Account is Already Registered With That Email Address"}


if __name__ == "__main__":
    app.run(debug = True)