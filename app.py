from flask import Flask,render_template,request,session,flash,redirect,url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from webforms import  SearchForm
import re

app = Flask(__name__,template_folder="templates")
app.secret_key="hello"

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Avoids a warning

db = SQLAlchemy(app)

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False,unique=True)
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
@app.route("/intro")
def index():
   return render_template("intro.html")

@app.route("/home")
def home():

   if "user" in session:
      posts = Post.query.all()
      user=session.get("username")
      return render_template("home.html", user=user, posts=posts)
      
   else:
      flash("You aren't logged in. Please log in to see the reviews.")
      return render_template("home.html")

@app.route("/database")
def database():
   return render_template("database.html",values=Users.query.all())

# Pass Stuff To Navbar
@app.context_processor
def base():
	form = SearchForm()
	return dict(form=form)

@app.route('/search', methods=['GET', 'POST'])
def search():
    form = SearchForm()
    
    # Handle form submission
    if form.validate_on_submit():
        search_term = form.searched.data.strip()
        if search_term:  # Only search if term is not empty
            posts = Post.query.filter(
                Post.text.ilike(f'%{search_term}%')
            ).order_by(Post.id.desc()).all()
            
            return render_template('search.html',
                               form=form,
                               searched=search_term,
                               posts=posts)
        else:
            flash('Please enter a search term', 'warning')
            return redirect(url_for('search'))
    
    # Handle direct access to /search without submission
    flash('Please enter a search term first', 'info')
    return redirect(url_for('home')) 

@app.route("/signup",methods=["GET","POST"])
def signup():
    if request.method == "POST":
      email=request.form["email"]
      username=request.form["username"]
      actual_password=request.form["password"]
      confirm_password=request.form["confirm-password"]
      

      
      if not email  or not username  or not actual_password:
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
            password=generate_password_hash(actual_password,method="pbkdf2:sha256")
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

      
      if found_user:
         if check_password_hash(found_user.password,password):
            session["user"]=found_user.username
            return redirect(url_for("home"))
         else:
            flash("Incorrect password","Error")
      else:
         flash("Users does not exist","Error")
         return redirect(url_for("login"))
   return render_template("Login.html")

@app.route("/logout")
def logout():
   session.pop("user",None)
   return redirect(url_for("login"))

@app.route('/delete/<email>')
def erase(email):
    data = Users.query.filter_by(email=email).first()
    db.session.delete(data)
    db.session.commit()
    flash("User deleted successfully.")
    return redirect(url_for("signup"))

@app.route("/create-post", methods=['GET', 'POST'])
def create_post():
   if "user" not in session:
      flash("Please login to create a post", category="error")
      return render_template("Login.html")

   username=session.get("user")
   user = Users.query.filter_by(username=username).first()

   if not user:
      flash("User not found", category="error")

   if request.method == "POST":
        text = request.form.get('text')

        if not text:
            flash("Post cannot be empty", category='error')
        else:
            post = Post(text=text, author=username)
            db.session.add(post)
            db.session.commit()
            flash('Post created!', category='success')
            return redirect(url_for('home'))
   return render_template("create_post.html")

@app.route("/delete-post/<id>", methods=['GET','POST'])
def delete_post(id):
   post = Post.query.filter_by(id=id).first()

   if not post:
      flash("Post doesn't exist", category="error")
   elif session.get("user") != post.author:
      flash("You don't have permission to delete this post.", category="error")
   else:
      db.session.delete(post)
      db.session.commit()
      flash("Post deleted", category="success")
   return redirect(url_for('home'))

@app.route("/edit-post/<id>", methods=['GET', 'POST'])
def edit_post(id):
    post = Post.query.filter_by(id=id).first()

    if not post:
        flash("Post doesn't exist", category="error")
        return redirect(url_for('home'))
    
    if session.get("user") != post.author:
        flash("You don't have permission to edit this post.", category="error")
        return redirect(url_for('home'))

    if request.method == 'POST':
        text = request.form.get('text')
        
        if not text:
            flash("Post cannot be empty", category='error')
        else:
            post.text = text  # Update the post content
            db.session.commit()
            flash("Post updated successfully", category='success')
            return redirect(url_for('home'))
    
    # For GET request, show the edit form with current post content
    return render_template('edit_post.html', post=post)

@app.route("/posts/<username>")
def posts(username):
   user = Users.query.filter_by(username=username).first()

   if not user:
      flash("No user with that username exists", category="error")
      return redirect(url_for("home"))

   posts = Post.query.filter_by(author=user.username).all()
   user=session.get("username")

   return render_template("posts.html", user=user, posts=posts, username=username)

if __name__ == '__main__':  
   with app.app_context():  # Needed for DB operations outside a request
        db.create_all() 
   app.run(debug=True)
