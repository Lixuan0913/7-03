from flask import Flask,render_template,request,session,flash,redirect,url_for,flash, Blueprint
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import re

app = Flask(__name__,template_folder="templates")
app.secret_key="hello"

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Avoids a warning

db = SQLAlchemy(app)

class Users(db.Model):
    username = db.Column(db.String(100), primary_key = True)
    email = db.Column("email",db.String(100),unique=True)
    password = db.Column(db.String(12))
    display_name = db.Column(db.String(100))

    def __init__(self,email,username,password,display_name):
        self.email=email
        self.username=username
        self.password=password
        self.display_name=display_name



class Post(db.Model):
    username = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100), db.ForeignKey('users.username'))

@app.route("/home")
def home():
   user=session.get("user")

   if user:
      return f"hello {user}"
   
   else:
      return "Not user log in"

@app.route("/database")
def database():
   return render_template("database.html",values=Users.query.all())


@app.route("/signup",methods=["GET","POST"])
def signup():
    if request.method == "POST":
      email=request.form["email"]
      username=request.form["username"]
      display_name=request.form["nickname"]
      actual_password=request.form["password"]
      confirm_password=request.form["confirm-password"]
      

      
      if not email  or not username  or not actual_password  or not display_name:
           flash("Please fill out all field")
           return redirect(url_for("signup"))
      
      pattern=r'^[a-zA-Z\.]+@(student\.mmu\.edu\.my|mmu\.edu\.my)$'

      if not re.match(pattern,email):
          flash("Please use mmu email")
          return redirect(url_for("signup"))
         
      if actual_password != confirm_password:
          flash("Passwords does not match","Error")
          return redirect(url_for("signup"))
         
      existing_user = Users.query.filter_by(username=username).first()
      if existing_user:
         flash("User already exist", "Error")
         return redirect(url_for("signup"))
      
      try:
        user = Users(
            email=email,
            username=username,
            password=generate_password_hash(actual_password,method="pbkdf2:sha256"),
            display_name=display_name
            )
        db.session.add(user)
        db.session.commit()
        flash("Signup successful!", "Success")
        return redirect(url_for("login"))
      except Exception as e:
         db.session.rollback()
         flash("Error while saving to database: " + str(e), "Error")
         return redirect(url_for("signup"))

    
    return render_template("Signup.html")

@app.route("/login",methods=["GET","POST"])
def login():
   
   if request.method == "POST":
      username=request.form["username"]
      password=request.form["password"]

      found_user = Users.query.filter_by(username=username).first()

      
      if found_user :
         if check_password_hash(found_user.password,password):
            session["user"]=found_user.username
            return redirect(url_for("home"))
         else:
            flash("Please check your username and password")
   return render_template("Login.html")

@app.route('/delete/<email>')
def erase(email):
    data = Users.query.filter_by(email=email).first()
    db.session.delete(data)
    db.session.commit()
    flash("User deleted successfully.")
    return redirect(url_for("signup"))

@app.route("/create-post", methods=['GET', 'POST'])
def create_post():
    if request.method == "POST":
        text = request.form.get('text')

        if not text:
            flash("Post cannot be empty", category='error')
        else:
            flash('Post created!', category='success')

    return render_template("create_post.html")

if __name__ == '__main__':  
   with app.app_context():  # Needed for DB operations outside a request
        db.create_all() 
   app.run(debug=True)
