
from flask import Flask,render_template,request,session,flash,redirect,url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from webforms import SearchForm
from flask_migrate import Migrate
from datetime import datetime
import re
from werkzeug.utils import secure_filename
import uuid as uuid
import os

app = Flask(__name__,template_folder="templates")
app.secret_key="hello"
UPLOAD_FOLDER="static/profile/pics"
POST_IMAGE_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'reviewpic')
app.config['UPLOAD_FOLDER']=UPLOAD_FOLDER
app.config['POST_IMAGE_FOLDER']=POST_IMAGE_FOLDER
os.makedirs(POST_IMAGE_FOLDER, exist_ok=True)

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Avoids a warning

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False,unique=True)
    email = db.Column("email",db.String(100), nullable=False)
    password = db.Column(db.String(12), nullable=False)  
    image_file=db.Column(db.String(100),nullable=False,default='default.jpg')
    identity=db.Column(db.String(20),nullable=False)
    post = db.relationship('Post', backref='users', passive_deletes=True) # Sets a relationship with Post table for 1 to Many relationship
    comments = db.relationship('Replies', backref='users', passive_deletes=True) 

    def __init__(self,email,username,password):
        self.email=email
        self.username=username
        self.password=password
      
        self.identity=self.get_identity()

    def get_identity(self):
        if self.email.endswith("@mmu.edu.my"):
           return "lecturer"
        if self.email.endswith("@student.mmu.edu.my"):
           return "student"
       
    def has_helpful_feedback(self, post_id):
        feedback = Feedback.query.filter_by(
            user_id=self.id,
            post_id=post_id,
            is_helpful=True
        ).first()
        return feedback is not None
    
    def has_not_helpful_feedback(self, post_id):
        feedback = Feedback.query.filter_by(
            user_id=self.id,
            post_id=post_id,
            is_helpful=False
        ).first()
        return feedback is not None
        
post_tags = db.Table('post_tags',
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True)
)

class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete="CASCADE"))

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ratings = db.Column(db.Integer)
    text = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100), db.ForeignKey('users.username', ondelete="CASCADE"), nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)  # Add this line
    comments = db.relationship('Replies', backref='post', cascade="all, delete-orphan", passive_deletes=True)
    tags = db.relationship('Tag', secondary=post_tags, backref=db.backref('posts', lazy='dynamic'))
    images=db.relationship('Image', backref='post', cascade="all, delete-orphan", passive_deletes=True)
    helpful_count = db.Column(db.Integer, default=0) 
    not_helpful_count = db.Column(db.Integer, default=0)    

class Replies(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), db.ForeignKey('users.username', ondelete="CASCADE"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete="CASCADE"), nullable=False)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    is_default = db.Column(db.Boolean, default=False)  # True for predefined tags

class Feedback(db.Model):  # Add this new class
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    is_helpful = db.Column(db.Boolean, nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', name='_user_post_uc'),
    )
    

@app.route("/")
@app.route("/home")
def home():

   if "user" in session:
      posts = Post.query.all()
      username = session["user"]
      user = Users.query.filter_by(username=username).first()
      return render_template("home.html", user=user, posts=posts)
      
   else:
      flash("You aren't logged in. Please login or signup to see the reviews.", "danger")
      return render_template("intro.html")

@app.route("/database")
def database():
   return render_template("database.html",values=Users.query.all())


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
          flash("Passwords does not match","danger")
          return redirect(url_for("signup"))
         
      existing_user = Users.query.filter_by(username=username).first()
      if existing_user:
         flash("User already exist", "danger")
         return redirect(url_for("signup"))
      
      try:
        user = Users(
            email=email,
            username=username,
            password=generate_password_hash(actual_password,method="pbkdf2:sha256")
            )
        db.session.add(user)
        db.session.commit()
        flash("Signup successful!", "success")
        return redirect(url_for("login"))
      
      except Exception as e:
         db.session.rollback()
         flash("Error while saving to database: " + str(e), "danger")
         return redirect(url_for("signup"))

    
    return render_template("Signup.html")
@app.context_processor
def inject_current_user():
    # Get username from session
    username = session.get('user')
    
    # If user is logged in, get their full user object
    if username:
        current_user = Users.query.filter_by(username=username).first()
        return {'current_user': current_user}
    return {'current_user': None}

@app.route("/login",methods=["GET","POST"])
def login():
   
   if request.method == "POST":
      username=request.form["username"]
      password=request.form["password"]

      found_user = Users.query.filter_by(username=username).first()

      
      if found_user:
         if check_password_hash(found_user.password,password):
            session["user"]=found_user.username
            session["user_id"] = found_user.id
            flash("Login Successful","success")
            return redirect(url_for("home"))
         else:
            flash("Incorrect password","danger")
      else:
         flash("Users does not exist","danger")
         return redirect(url_for("login"))
   return render_template("Login.html")

@app.route("/logout")
def logout():
   session.pop("user",None)
   flash("You have been logout","success")
   return redirect(url_for("login"))


@app.route('/delete/<email>',methods=["POST"])
def delete_user(email):
    if request.method=="POST":
      data = Users.query.filter_by(email=email).first()
      db.session.delete(data)
      db.session.commit()
      flash("User deleted successfully.","success")
    else:
        flash("User not found.", "danger")
    return redirect(url_for("signup"))

def create_tags():
    default_tags=['Lecturer','Facilities','Food']
    existing_tags={tag.name for tag in Tag.query.filter(Tag.name.in_(default_tags)).all()}
    
    new_tags = [Tag(name=tag_name, is_default=True)
        for tag_name in default_tags
        if tag_name not in existing_tags
    ]

    if new_tags:
        db.session.bulk_save_objects(new_tags)
        db.session.commit()

@app.route("/create-post", methods=['GET', 'POST'])
def create_post():
   if "user" not in session:
      flash("Please login to create a post", category="danger")
      return redirect(url_for("login"))
   
   create_tags()

   username=session.get("user")
   user = Users.query.filter_by(username=username).first()

   if not user:
      flash("User not found", category="danger")
    
   default_tags = Tag.query.filter_by(is_default=True).all()

   if request.method == "POST":
        text = request.form.get('text', '').strip()  # Get and clean the text
        ratings = request.form.get('ratings')
        selected_default_tags = request.form.getlist('default_tags')
        custom_tags = request.form.get('custom_tags',' ').strip()
        upload_files = request.files.getlist('picture')

        if not text:
            flash("Post cannot be empty", category='danger')
            return render_template("create_post.html",default_tags=default_tags)
        if not ratings:
            flash("Select a rating", category="danger")
            return render_template("create_post.html", text=text,default_tags=default_tags)
        else:
            post = Post(text=text, author=username, ratings=int(ratings) if ratings else None)
            db.session.add(post)
            db.session.flush()  # <--- Flush here to get post.id


            #Process default tags
            for tag_id in selected_default_tags:
                tag=Tag.query.get(tag_id)
                if tag:
                    post.tags.append(tag)

            # Process custom tags
            if custom_tags:
                  
                for tag_name in [t.strip().lower() for t in custom_tags.split(',') if t.strip()]:

                    # Check if tag exists (case-insensitive)
                    tag = Tag.query.filter(db.func.lower(Tag.name) == tag_name).first()

                    if not tag:  # Create new tag if it doesn't exist
                      tag = Tag(name=tag_name, is_default=False)
                      db.session.add(tag)
                      db.session.flush()

                    if tag not in post.tags: # prevent duplicate
                      post.tags.append(tag)

            for file in upload_files:
                filename = secure_filename(file.filename)
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext in ['.jpg', '.jpeg', '.png']:
                    # Generate a unique filename to prevent collisions
                    filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
                    file_path = os.path.join(app.config['POST_IMAGE_FOLDER'], filename)
                    
                    try:
                        file.save(file_path)
                        # Create image record in database
                        image = Image(filename=filename, post_id=post.id)
                        db.session.add(image)
                    except Exception as e:
                        flash(f"Error saving image: {str(e)}", category='danger')
                        continue

            db.session.commit()
            flash('Post created!', category='success')
            return redirect(url_for('home'))
   return render_template("create_post.html",default_tags=default_tags)

@app.route("/delete-post/<id>", methods=['GET','POST'])
def delete_post(id):
    post = Post.query.filter_by(id=id).first()

    if not post:
        flash("Post doesn't exist", category="danger")
    elif session.get("user") != post.author:
        flash("You don't have permission to delete this post.", category="danger")
    else:
        for image in post.images:
            try:
                image_path = os.path.join(POST_IMAGE_FOLDER, image.filename)
                if os.path.exists(image_path):
                    os.remove(image_path)  # Delete the file
            except Exception as e:
                flash(f"Failed to delete image {image.filename}: {e}")

        # First delete all comments associated with the post
        Replies.query.filter_by(post_id=post.id).delete()
        # Then delete the post
        db.session.delete(post)
        db.session.commit()
        flash("Post and its comments are deleted", category="success")

     # Check if the referrer is the profile page
    referrer = request.referrer
    if referrer and '/profile/' in referrer:
       # Extract username from referrer URL
       profile_username = referrer.split('/profile/')[-1].split('?')[0]
       return redirect(url_for('profile', username=profile_username))
    
    return redirect(url_for('home'))

@app.route("/edit-post/<id>", methods=['GET', 'POST'])
def edit_post(id):
    post = Post.query.filter_by(id=id).first()

    if not post:
        flash("Post doesn't exist", category="danger")
        return redirect(url_for('home'))
    
    if session.get("user") != post.author:
        flash("You don't have permission to edit this post.", category="danger")
        return redirect(url_for('home'))

    if request.method == 'POST':
        text = request.form.get('text')
        ratings = request.form.get('ratings')
        
        if not text:
            flash("Post cannot be empty", category='danger')
        else:
            post.text = text
            post.ratings = int(ratings) if ratings else None
            db.session.commit()
            flash("Post updated successfully", category='success')
            return redirect(url_for('home'))
    
    # For GET request, show the edit form with current post content
    return render_template('edit_post.html', post=post)



@app.route("/posts/<username>")
def posts(username):
   user = Users.query.filter_by(username=username).first()

   if not user:
      flash("No user with that username exists", category="danger")
      return redirect(url_for("home"))
   
   posts = Post.query.options(db.joinedload(Post.images), db.joinedload(Post.tags))\
        .filter_by(author=user.username)\
        .order_by(Post.date_posted.desc())\
        .all()
   
   current_user=session.get("username")

   return render_template("posts.html", user=current_user, posts=posts, username=username)

@app.route("/view_post/<int:post_id>")
def view_post(post_id):
    post = Post.query.options(
        db.joinedload(Post.images),
        db.joinedload(Post.tags),
        db.joinedload(Post.comments).joinedload(Replies.users)
    ).filter_by(id=post_id).first()

    if not post:
        flash("Post not found", category="error")
        return redirect(url_for("home"))
    
    return render_template("view_post.html", post=post)

@app.route("/create-comment/<post_id>", methods=["POST"])
def create_comment(post_id):
   text = request.form.get('text')
   username=session.get("user")
   user = Users.query.filter_by(username=username).first()

   if not text :
      flash("Comment cannot be empty", category="danger")
   else:
      post = Post.query.filter_by(id=post_id)
      if post:
         comment = Replies(text=text, author=username, post_id=post_id)
         db.session.add(comment)
         db.session.commit()
         flash("Comment posted", category="success")
      else:
         flash("Post doesn't exist", category="danger")
   
   return redirect(url_for('home'))

@app.route("/delete-comment/<comment_id>")
def delete_comment(comment_id):
   username=session.get("user")
   user = Users.query.filter_by(username=username).first()
   comment = Replies.query.filter_by(id=comment_id).first()

   if not comment:
      flash("Comment doesn't exist", category="danger")
   elif session.get("user") != comment.author and session.get("user") != comment.post.author:
      flash("You don't have permission to delete this comment", category="danger")
   else:
      db.session.delete(comment)
      db.session.commit()
     # Check if the referrer is the profile page
   referrer = request.referrer
   if referrer and '/profile/' in referrer:
       # Extract username from referrer URL
       profile_username = referrer.split('/profile/')[-1].split('?')[0]
       return redirect(url_for('profile', username=profile_username))
   
   return redirect(url_for('home'))

@app.route("/edit-comment/<comment_id>", methods=["GET", "POST"])
def edit_comment(comment_id):
   comment = Replies.query.filter_by(id=comment_id).first()

   if not comment:
        flash("Post doesn't exist", category="danger")
        return redirect(url_for('home'))
    
   if session.get("user") != comment.author:
        flash("You don't have permission to edit this post.", category="danger")
        return redirect(url_for('home'))

   if request.method == 'POST':
        text = request.form.get('text')
        
        if not text:
            flash("Post cannot be empty", category='danger')
        else:
            comment.text = text  # Update the post content
            db.session.commit()
            flash("Comment updated successfully", category='success')
            return redirect(url_for('home'))
    
   return render_template('edit_comment.html', comment=comment)

# Pass Stuff To Navbar
@app.context_processor
def base():
	form = SearchForm()
	return dict(form=form)

@app.route('/search', methods=['GET', 'POST'])
def search():
    form = SearchForm()
    
    if form.validate_on_submit():
        search_term = form.searched.data.strip()
        if search_term:
            # Debug: Print search term
            print(f"Searching for: {search_term}")
            
            # Search in posts
            posts = Post.query.filter(
                Post.text.ilike(f'%{search_term}%')
            ).order_by(Post.id.desc()).all()
            print(f"Found {len(posts)} post matches")
            
            # Search in comments
            comments = Replies.query.filter(
                Replies.text.ilike(f'%{search_term}%')
            ).order_by(Replies.id.desc()).all()
            print(f"Found {len(comments)} comment matches")
            
            # Get all post IDs that have matching comments
            post_ids_with_matching_comments = {comment.post_id for comment in comments}
            print(f"Posts with matching comments: {post_ids_with_matching_comments}")
            
            # Get posts that have matching comments but didn't match in post text
            additional_posts = Post.query.filter(
                Post.id.in_(post_ids_with_matching_comments),
                ~Post.id.in_([post.id for post in posts])
            ).all()
            print(f"Found {len(additional_posts)} additional posts via comments")
            
            # Combine all posts to display (remove duplicates)
            all_posts = []
            seen_post_ids = set()
            for post in posts + additional_posts:
                if post.id not in seen_post_ids:
                    all_posts.append(post)
                    seen_post_ids.add(post.id)
            
            print(f"Total posts to display: {len(all_posts)}")
            
            # Create a dictionary to organize comments by post ID
            comments_by_post = {}
            for comment in comments:
                if comment.post_id not in comments_by_post:
                    comments_by_post[comment.post_id] = []
                comments_by_post[comment.post_id].append(comment)
            
            return render_template('search.html',
                               form=form,
                               searched=search_term,
                               posts=all_posts,
                               comments_by_post=comments_by_post)
        else:
            flash('Please enter a search term', 'warning')
            return redirect(url_for('search'))
    
    flash('Please enter a search term first', 'info')
    return redirect(url_for('home'))

@app.route("/profile/<username>", methods=["GET", "POST"])
def profile(username):
    profile_user = Users.query.filter_by(username=username).first()
    if not profile_user:
        flash("User not found")
        return redirect(url_for("Login"))
    
    # Get all posts by this user, ordered by newest first
    user_posts = Post.query.filter_by(author=username).order_by(Post.id.desc()).all()
   
    image_file = url_for('static', filename='profile/pics/' + profile_user.image_file)
    return render_template("Profile.html", user=profile_user, image_file=image_file,posts=user_posts)

@app.route("/update/<username>", methods=["GET", "POST"])
def update(username):
    current_user = Users.query.filter_by(username=username).first()
    if not current_user:
        flash("User not found")
        return redirect(url_for("Login"))
    

    
    if request.method == "POST":
        # Get form data
        new_username = request.form.get("username")
        new_password = request.form.get("password")
        confirm_password = request.form.get("confirm-password")
        image_file = request.files.get("profile-picture")
        reset_picture=request.form.get("reset_picture")
        
        # Update username
        if new_username:
            current_user.username = new_username

        # Update password if provided
        if new_password:
            if new_password == confirm_password:
                current_user.password = generate_password_hash(new_password)
            else:
                flash("Password does not match", "danger")
                return redirect(url_for("update", username=current_user.username))
            
        


        # Handle image upload
        if image_file and image_file.filename != '':

            # Delete old image if it's not the default
            if current_user.image_file != 'default.jpg':
              try:
                old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], current_user.image_file)
                if os.path.exists(old_image_path):
                   os.remove(old_image_path)
              except Exception as e:
                 flash(f"Could not delete old image: {str(e)}", "warning")


            filename = secure_filename(image_file.filename)
            file_ext = os.path.splitext(filename)[1].lower()  # Get the file extension
    
            if file_ext not in ['.jpg', '.jpeg', '.png']:
              flash("Only JPG or PNG are allowed","alert")
              return redirect(url_for("update", username=current_user.username))

            unique_filename = str(uuid.uuid1()) + '_' + filename
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            image_file.save(image_path)
            current_user.image_file = unique_filename

        if reset_picture:
            if current_user.image_file != 'default.jpg':

              try:
                 old_path = os.path.join(app.config['UPLOAD_FOLDER'], current_user.image_file)
                 if os.path.exists(old_path):
                    os.remove(old_path)
              except Exception as e:
                 flash(f"Couldn't delete old image: {str(e)}", "warning")

            current_user.image_file = 'default.jpg'
            flash("Profile picture reset to default", "success")

        try:
            db.session.commit()
            flash("Update Successful", "success")
            return redirect(url_for("profile", username=current_user.username))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating profile: {str(e)}", "danger")

    return render_template("Update.html", user=current_user, current_image=url_for('static', filename='profile/pics/' + current_user.image_file))

@app.route("/feedback/<int:post_id>/<action>")
def feedback(post_id, action):
    if "user" not in session:
        flash("Please login to provide feedback", "danger")
        return redirect(url_for('login'))
    
    user = Users.query.filter_by(username=session["user"]).first()
    post = Post.query.get_or_404(post_id)
    
    # Check if user already gave feedback
    existing_feedback = Feedback.query.filter_by(
        user_id=user.id,
        post_id=post_id
    ).first()
    
    if action == "helpful":
        if existing_feedback:
            if existing_feedback.is_helpful:
                # User is removing their helpful vote
                post.helpful_count -= 1
                db.session.delete(existing_feedback)
            else:
                # User is changing from not helpful to helpful
                post.not_helpful_count -= 1
                post.helpful_count += 1
                existing_feedback.is_helpful = True
        else:
            # New helpful vote
            post.helpful_count += 1
            feedback = Feedback(user_id=user.id, post_id=post_id, is_helpful=True)
            db.session.add(feedback)
    
    elif action == "not-helpful":
        if existing_feedback:
            if not existing_feedback.is_helpful:
                # User is removing their not helpful vote
                post.not_helpful_count -= 1
                db.session.delete(existing_feedback)
            else:
                # User is changing from helpful to not helpful
                post.helpful_count -= 1
                post.not_helpful_count += 1
                existing_feedback.is_helpful = False
        else:
            # New not helpful vote
            post.not_helpful_count += 1
            feedback = Feedback(user_id=user.id, post_id=post_id, is_helpful=False)
            db.session.add(feedback)
    
    db.session.commit()
    
    return redirect(request.referrer or url_for('home'))

if __name__ == '__main__':  
   with app.app_context():  # Needed for DB operations outside a request
        db.create_all() 
   app.run(debug=True)
