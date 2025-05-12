
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
ITEM_IMAGE_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'itempic')
app.config['UPLOAD_FOLDER']=UPLOAD_FOLDER
app.config['POST_IMAGE_FOLDER']=POST_IMAGE_FOLDER
app.config['ITEM_IMAGE_FOLDER']=ITEM_IMAGE_FOLDER
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
        
class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete="CASCADE"))

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ratings = db.Column(db.Integer, nullable=True)
    text = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100), db.ForeignKey('users.username', ondelete="CASCADE"), nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)  # Add this line
    comments = db.relationship('Replies', backref='post', cascade="all, delete-orphan", passive_deletes=True)
    images=db.relationship('Image', backref='post', cascade="all, delete-orphan", passive_deletes=True)
    helpful_count = db.Column(db.Integer, default=0) 
    not_helpful_count = db.Column(db.Integer, default=0)    
    item_id = db.Column(db.Integer, db.ForeignKey('item.id', ondelete="CASCADE"))
    status = db.Column(db.String(20), default='visible')

class Replies(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), db.ForeignKey('users.username', ondelete="CASCADE"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete="CASCADE"), nullable=False)

item_tags = db.Table('item_tags',
    db.Column('item_id', db.Integer, db.ForeignKey('item.id', ondelete="CASCADE"), primary_key=True),   
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id', ondelete="CASCADE"), primary_key=True)
)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    is_default = db.Column(db.Boolean, default=False)  # True for predefined tags

class Item_Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id', ondelete="CASCADE"))

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140))
    description = db.Column(db.Text)
    images=db.relationship('Item_Image', backref='item', cascade="all, delete-orphan", passive_deletes=True)
    tags = db.relationship('Tag', secondary=item_tags, backref=db.backref('items', lazy='dynamic'))
    posts = db.relationship('Post', backref='item', cascade="all, delete-orphan", passive_deletes=True)

class Feedback(db.Model):  # Add this new class
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    is_helpful = db.Column(db.Boolean, nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', name='_user_post_uc'),
    )
    
class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reported_content_id = db.Column(db.Integer, nullable=False)
    content_type = db.Column(db.String(10), nullable=False)
    reason = db.Column(db.String(50), nullable=False)
    details = db.Column(db.String(200))

    reporter = db.relationship('Users', backref='reports')

# Simple profanity filter
class ProfanityFilter:
    def __init__(self):
        # List of inappropriate words (customize this list)
        self.banned_words = [
            'shit', 'fuck', 'asshole', 'bitch', 'cunt',
            'dick', 'pussy', 'bastard', 'whore', 'slut',
            'fag', 'nigger', 'retard', 'damn', 'hell',
            'suck', 'nigga', 'fucking', 'ass'
        ]
        
        # Create variations with common misspellings
        self.word_variations = []
        for word in self.banned_words:
            self.word_variations.append(word)
            self.word_variations.append(word.replace('i', '1'))
            self.word_variations.append(word.replace('i', '!'))
            self.word_variations.append(word.replace('e', '3'))
            self.word_variations.append(word.replace('a', '4'))
            self.word_variations.append(word.replace('o', '0'))
            self.word_variations.append(word.replace('u', '0'))
            self.word_variations.append(word + 'head')
            self.word_variations.append(word + 'hole')
    
    def contains_profanity(self, text):
        """Check if text contains any banned words"""
        if not text:
            return False
            
        text_lower = text.lower()
        words = re.findall(r'\w+', text_lower)
        return any(bad_word in self.word_variations for bad_word in words)
    
# Create a global instance
profanity_filter = ProfanityFilter()
    
@app.route("/")
@app.route("/home")
def home():
   user=session.get("user")
   review_item=Item.query.options(
        db.joinedload(Item.images),
        db.joinedload(Item.posts)
    ).all()
   if "user" in session:
      username = session["user"]
      user = Users.query.filter_by(username=username).first()
      return render_template("home.html", user=user, items=review_item)
      
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

@app.route("/create-post/<int:item_id>", methods=['GET', 'POST'])
def create_post(item_id):
   if "user" not in session:
      flash("Please login to create a post", category="danger")
      return redirect(url_for("login"))

   username=session.get("user")
   user = Users.query.filter_by(username=username).first()

   if not user:
        flash("User not found", category="danger")
    
   item = Item.query.get_or_404(item_id)


   if request.method == "POST":
        text = request.form.get('text', '').strip()  # Get and clean the text
        ratings = request.form.get('ratings')
        upload_files = request.files.getlist('picture')

        if not text:
            flash("Post cannot be empty", category='danger')
            return render_template("create_post.html")
        if not ratings:
            flash("Select a rating", category="danger")
            return render_template("create_post.html", text=text)
        else:
            if profanity_filter.contains_profanity(text):
                flash("Your comment contains inappropriate language and cannot be posted", category="danger")
            else:
                post = Post(text=text, author=username, ratings=int(ratings), item_id=item.id)
                db.session.add(post)
                db.session.flush()  # <--- Flush here to get post.id


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
                return redirect(url_for('view_item', item_id=item.id))  # Redirect to item page
   return render_template("create_post.html", item=item)
                

@app.route("/delete-post/<int:id>", methods=['GET','POST'])
def delete_post(id):
    item_id = request.args.get('item_id', type=int)
    post = Post.query.filter_by(id=id).first()

    if not post:
        flash("Post doesn't exist", category="danger")
    elif session.get("user") != post.author:
        flash("You don't have permission to delete this post.", category="danger")
    else:
        post.status = 'removed'
        post.text = "[This post has been removed]"
        post.ratings = None

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
        db.session.commit()
        flash("Post has been removed", category="success")

     # Check if the referrer is the profile page
    referrer = request.referrer
    if referrer and '/profile/' in referrer:
       # Extract username from referrer URL
       profile_username = referrer.split('/profile/')[-1].split('?')[0]
       return redirect(url_for('profile', username=profile_username))
    
    return redirect(url_for('view_item', item_id=item_id))

@app.route("/edit-post/<id>", methods=['GET', 'POST'])
def edit_post(id):
    post = Post.query.filter_by(id=id).first()
    item_id = request.args.get('item_id', type=int)

    if not post:
        flash("Post doesn't exist", category="danger")
        return redirect(url_for('home'))
    
    if session.get("user") != post.author:
        flash("You don't have permission to edit this post.", category="danger")
        return redirect(url_for('home'))

    if request.method == 'POST':
        text = request.form.get('text')
        ratings = request.form.get('ratings')
        upload_image=request.files.getlist("images")
        delete_images=request.form.getlist('delete_images')
        
        if not text:
            flash("Post cannot be empty", category='danger')
        else:
            if profanity_filter.contains_profanity(text):
                flash("Your comment contains inappropriate language and cannot be posted", category="danger")
            else:
                post.text = text
                post.ratings = int(ratings) if ratings else None
                

        # Handle image uploads
        if upload_image:
            for file in upload_image:
                if file.filename != '':
                    # Save the file
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


            
            # Handle image deletions
        if delete_images:
            for image_id in delete_images:
                image = Image.query.get(image_id)
                if image and image.post_id == post.id:  
                    # Delete file from filesystem
                    filepath = os.path.join(app.config['POST_IMAGE_FOLDER'], image.filename)
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    # Delete from database
                    db.session.delete(image)

            db.session.commit()
            flash("Post updated successfully", category='success')
            return redirect(url_for('view_item',item_id=item_id))
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

@app.route("/view_post/<int:post_id>/item/<int:item_id>")
def view_post(post_id, item_id):
    post = Post.query.options(
        db.joinedload(Post.images),
        db.joinedload(Post.comments).joinedload(Replies.users)
    ).filter_by(id=post_id).first()
    item = Item.query.get_or_404(item_id)

    if not post:
        flash("Post not found", category="error")
        return redirect(url_for("home"))
    
    return render_template("view_post.html", post=post,item=item)

@app.route("/create-comment/<post_id>", methods=["POST"])
def create_comment(post_id):
    text = request.form.get('text')
    username=session.get("user")
    post = Post.query.filter_by(id=post_id).first()

    if not text :
      flash("Comment cannot be empty", category="danger")
    elif not post:
       flash("Comment doesn't exist", category="danger")
    else:
        if profanity_filter.contains_profanity(text):
            flash("Your comment contains inappropriate language and cannot be posted", category="danger")
        else:
            if post:
                comment = Replies(text=text, author=username, post_id=post_id)
                db.session.add(comment)
                db.session.commit()
                flash("Comment posted", category="success")
            else:
                flash("Post doesn't exist", category="danger")
   
    return redirect(url_for('view_item', item_id=post.item_id))

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

   post = comment.post
   item_id = post.item_id
   
   if request.method == 'POST':
        text = request.form.get('text')
        
        if not text:
            flash("Post cannot be empty", category='danger')
        else:
            if profanity_filter.contains_profanity(text):
                flash("Your comment contains inappropriate language and cannot be posted", category="danger")
            
            comment.text = text  # Update the post content
            db.session.commit()
            flash("Comment updated successfully", category='success')
            return redirect(url_for('view_item', item_id=item_id))
    
   return render_template('edit_comment.html', comment=comment, post=post)

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

@app.route("/additem", methods=["GET", "POST"])
def add_item():
    
    create_tags()

    default_tags = Tag.query.filter_by(is_default=True).all()


    if request.method == "POST":
        name=request.form.get("name")
        selected_default_tags = request.form.getlist('default_tags')
        custom_tags = request.form.get('custom_tags',' ').strip()
        description=request.form.get("description")
        review_pic=request.files.getlist('review_picture')

        if not (name and description):
            flash("Please enter all required fields", "danger")
            return redirect(url_for('add_item'))
        
        try:
            # Create the Item
            new_item = Item(
                name=name,
                description=description,
            )
            db.session.add(new_item)
            db.session.flush()  # Get the ID for the new item

            # Process default tags
            for tag_id in selected_default_tags:
                tag = Tag.query.get(tag_id)
                if tag:
                    new_item.tags.append(tag)

            # Process custom tags
            if custom_tags:
                for tag_name in [t.strip().lower() for t in custom_tags.split(',') if t.strip()]:
                    # Check if tag exists (case-insensitive)
                    tag = Tag.query.filter(db.func.lower(Tag.name) == tag_name).first()

                    if not tag:  # Create new tag if it doesn't exist
                        tag = Tag(name=tag_name, is_default=False)
                        db.session.add(tag)
                        db.session.flush()

                    if tag not in new_item.tags:
                        new_item.tags.append(tag)
            
            # Process images if any
            if review_pic:
                for file in review_pic:
                    if file.filename == '':  # Skip if no file selected
                        continue
                        
                    filename = secure_filename(file.filename)
                    file_ext = os.path.splitext(filename)[1].lower()
                    
                    if file_ext in ['.jpg', '.jpeg', '.png']:
                        # Generate unique filename
                        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
                        file_path = os.path.join(app.config['ITEM_IMAGE_FOLDER'], unique_filename)
                        
                        try:
                            file.save(file_path)
                            # Create image record linked to the item
                            new_image = Item_Image(
                                filename=unique_filename,
                                item_id=new_item.id
                            )
                            db.session.add(new_image)
                        except Exception as e:
                            flash(f"Error saving image: {str(e)}", "error")
                            continue
            
            db.session.commit()
            flash("Item added successfully!", "success")
            return redirect(url_for('home'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {str(e)}", "error")
            return redirect(url_for('home'))
    
    return render_template("add_item.html",default_tags=default_tags)

@app.route("/viewitem/<int:item_id>",methods=["GET", "POST"])
def view_item(item_id):
    item = Item.query.options(
        db.joinedload(Item.images),
        db.joinedload(Item.posts)
    ).get_or_404(item_id)
    return render_template('view_item.html', item=item)

@app.route("/deleteitem/<int:item_id>",methods=["GET", "POST"])
def delete_item(item_id, comment_id):
     item = Item.query.get_or_404(item_id)
     comment = Replies.query.filter_by(id=comment_id).first()

     try:
        # Delete associated images first
        for image in item.images:  # This assumes you have a relationship named 'images'
            # Delete image file from filesystem
            image_path = os.path.join(app.config['ITEM_IMAGE_FOLDER'], image.filename)
            try:
                if os.path.exists(image_path):
                    os.remove(image_path)
            except Exception as e:
                flash(f"Failed to delete image {image.filename}: {str(e)}")
                # Continue with deletion even if file deletion fails
        
        # Delete the item itself (which will cascade delete the images from database)
        db.session.delete(item)
        db.session.delete(comment)
        db.session.commit()
        flash("Item and all associated images deleted successfully", "success")
     except Exception as e:
        db.session.rollback()
        flash(f"Error deleting item: {str(e)}", "danger")
        
     return redirect(url_for('home'))

@app.route('/reported/post/<int:post_id>', methods = ['GET', 'POST'])
def report_post(post_id):
    if 'user' not in session:
        flash("Please login to report content", category="danger")
        return redirect(url_for('login'))
    
    post = Post.query.get_or_404(post_id)

    if request.method == 'POST':
        reason = request.form.get('reason')
        details = request.form.get('details')

        if not reason: 
            flash("Please select a reason for reporting", category="danger")
        else:
            #Checks if user already reported this post
            existing_report = Report.query.filter_by(
                reporter_id=session['user_id'],
                reported_content_id=post_id,
                content_type='post').first()
            
            if existing_report:
                flash("You have already reported this post", category="info")
            else:
                report = Report(
                    reporter_id=session['user_id'],
                    reported_content_id=post_id,
                    content_type='post',
                    reason=reason,
                    details=details
                )
                db.session.add(report)
                db.session.commit()
                flash("Your report has been submitted", category="success")

            return redirect(url_for('view_item', item_id=post.item_id))
    
    return render_template('report_form.html', content=post, content_type="post")

@app.route("/report/comment/<int:comment_id>", methods=["GET", "POST"])
def report_comment(comment_id):
    if 'user' not in session:
        flash("Please login to report content", category="danger")
        return redirect(url_for('login'))
    
    comment = Replies.query.get_or_404(comment_id)

    if request.method == 'POST':
        reason = request.form.get('reason')
        details = request.form.get('details')

        if not reason: 
            flash("Please select a reason for reporting", category="danger")
        else:
            #Checks if user already reported this post
            existing_report = Report.query.filter_by(
                reporter_id=session['user_id'],
                reported_content_id=comment_id,
                content_type='comment').first()
            
            if existing_report:
                flash("You have already reported this post", category="info")
            else:
                report = Report(
                    reporter_id=session['user_id'],
                    reported_content_id=comment_id,
                    content_type='comment',
                    reason=reason,
                    details=details
                )
                db.session.add(report)
                db.session.commit()
                flash("Your report has been submitted", category="success")

            return redirect(url_for('view_item', item_id=comment.post.item_id))
    
    return render_template('report_form.html', content=comment, content_type="comment")


if __name__ == '__main__':  
   with app.app_context():  # Needed for DB operations outside a request
        db.create_all() 
   app.run(debug=True)
