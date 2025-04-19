from flask import Flask,render_template,request,session,flash,redirect,url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key="hello"

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Avoids a warning

db = SQLAlchemy(app)
class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column("email",db.String(100), nullable=False)
    password = db.Column(db.String(12), nullable=False)
    post = db.relationship('Post', backref='users', passive_deletes=True) # Sets a relationship with Post table for 1 to Many relationship

    def __init__(self,email,username,password):
        self.email=email
        self.username=username
        self.password=password

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100), db.ForeignKey('users.username'), nullable=False)

@app.route("/")
@app.route("/home")
def home():
   posts = Post.query.all()
   user=session.get("username")

   if user:
      return render_template("home.html", user=user, posts=posts)
      
   else:
      return "User not logged in"

@app.route("/database")
def database():
   return render_template("database.html",values=Users.query.all())

@app.route("/signup",methods=["GET","POST"])
def signup():
    if request.method == "POST":
      email=request.form["email"]
      username=request.form["username"]
      password=request.form["password"]
      confirm_password=request.form["confirm-password"]
      existing_user = Users.query.filter_by(email=email).first()

      
      if email != " " or username != " " or password != " ":
         if password != confirm_password:
          flash("Passwords does not match","Error")
          return redirect(url_for("signup"))
      
         if existing_user:
            flash("Email already exists. Please use a different one.", "Error")
            return redirect(url_for("signup"))
      
         user = Users(email,username,password)
         db.session.add(user)
         db.session.commit()

      else:
         flash("Please fill out all field")
           
      flash("Signup successful!")
      return redirect(url_for("login"))
    
    return render_template("Signup.html")

@app.route("/login",methods=["GET","POST"])
def login():
   
   if request.method == "POST":
      email=request.form["email"]
      password=request.form["password"]

      found_user = Users.query.filter_by(email=email).first()
      
      if found_user and password == found_user.password:
         session["username"]=found_user.username
         return redirect(url_for("home"))
      else:
         flash("Please check your email and password")
   return render_template("Login.html")

@app.route('/delete/<email>')
def erase(email):
    data = Users.query.get(email)
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
            post = Post(text=text, author=session.get("username"))
            db.session.add(post)
            db.session.commit()
            flash('Post created!', category='success')
            return redirect(url_for('home'))
    return render_template("create_post.html")

@app.route("/delete-post/<id>", methods=['POST'])
def delete_post(id):
   post = Post.query.filter_by(id=id).first()

   if not post:
      flash("Post doesn't exist", category="error")
   elif session.get("username") != post.author:
      flash("You don't have permission to delete this post.", category="error")
   else:
      db.session.delete(post)
      db.session.commit()
      flash("Post deleted", category="success")
   return redirect(url_for('home'))

@app.route("/posts/<username>")
def posts(username):
   user = Users.query.filter_by(username=username).first()

   if not user:
      flash("No user with that username exists", category="error")
      return redirect(url_for("home"))

   posts = Post.query.filter_by(author=user.id).all()
   user=session.get("username")

   return render_template("posts.html", user=user, posts=posts, username=username)

if __name__ == '__main__':  
   with app.app_context():  # Needed for DB operations outside a request
        db.create_all() 
   app.run(debug=True)
