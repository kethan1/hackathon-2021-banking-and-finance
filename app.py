import json
import posixpath

from flask import Flask, render_template, session, request, flash, redirect
from flask_pymongo import PyMongo
from flask_qrcode import QRcode

app = Flask(__name__)
QRcode(app)

with open("config.json") as configFile:
    jsonConfig = json.load(configFile)
    app.config["MONGO_URI"] = jsonConfig["MONGODB_CONNECTION_URL"]
    app.secret_key = jsonConfig["SECRET_KEY"]

with open("events.json") as eventsFile:
    events = json.load(eventsFile)

mongo = PyMongo(app)

@app.route("/")
def home():
    if "logged_in" in session:
        logged_in = session["logged_in"]
        points = mongo.db.users.find_one({"email": session["logged_in"]["email"]})["points"]
    else:
        logged_in = None
        points = "Not Logged In"
    return render_template("home.html", logged_in = logged_in, points = points)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if "logged_in" in session and  session["logged_in"] != {}:
            flash("You are Already Logged In")
            return redirect("/")
        return render_template("login.html")
    elif request.method == "POST":
        email, password = request.form["email"], request.form["password"]
        found = mongo.db.users.find_one({"email": email})
        if found is not None:
            if found["password"] == password:
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
        return render_template("signup.html")
    elif request.method == "POST":
        email, password = request.form["email"], request.form["password"]
        found = mongo.db.users.find_one({"email": email})
        if found is None:
            mongo.db.users.insert_one({
                "email": email,
                "password": password,
                "admin": False,
                "points": 0
            })
            session["logged_in"] = {"email": email}
            flash("Successfully Signed Up")
            return redirect("/")
        else:
            flash("An Account is Already Registered With That Email Address")
            return redirect("/")

@app.route("/events")
def show_events():
    return render_template("events.html", events = events.items())

@app.route("/event_info/<eventName>")
def event_info(eventName):
    return render_template("event_info.html", eventName = eventName, eventData = events[eventName])

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
            return render_template("admin_generate.html", events = events_with_qr)
        else:
            flash("Not Logged In As Admin")
            return redirect("/")
    else:
        flash("Not Logged In")
        return redirect("/")

@app.route("/logout")
def logout():
    if "logged_in" in session:
        del session["logged_in"]
        flash("Logged Out")
    else:
        flash("Not Logged In")
    return redirect("/")

@app.route("/api/get_user_points", methods=["POST"])
def get_user_points():
    return {
        "points": mongo.db.users.find_one({"email": request.json["email"]})["points"]
    }

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

if __name__ == "__main__":
    app.run(debug = True)