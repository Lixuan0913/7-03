from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = "helloworld"

    return app

