from flask import Blueprint

auth = Blueprint("auth", __name__)

@auth.route("/login")
def login():
    return "Login"

@auth.route("/signup")
def signup():
    return "signup"

@auth.route("/signout")
def signout():
    return "signout"

@auth.route("/logout")
def logout():
    return "logout"