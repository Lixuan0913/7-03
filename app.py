from flask import Flask,render_template,request,session,flash,redirect,url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from webforms import SearchForm
from datetime import datetime
from mail_utils import init_mail, generate_token, confirm_token, send_verification_email,send_reset_email
import re
from werkzeug.utils import secure_filename
import uuid as uuid
import os

app = Flask(__name__,template_folder="templates")
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.secret_key="hello"
UPLOAD_FOLDER="static/profile/pics"
POST_IMAGE_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'reviewpic')
ITEM_IMAGE_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'itempic')
app.config['UPLOAD_FOLDER']=UPLOAD_FOLDER
app.config['POST_IMAGE_FOLDER']=POST_IMAGE_FOLDER
app.config['ITEM_IMAGE_FOLDER']=ITEM_IMAGE_FOLDER
os.makedirs(POST_IMAGE_FOLDER, exist_ok=True)
init_mail(app)

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Avoids a warning

db = SQLAlchemy(app)

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False,unique=True)
    email = db.Column("email",db.String(100), nullable=False)
    password = db.Column(db.String(12), nullable=False)  
    image_file=db.Column(db.String(100),nullable=False,default='default.jpg')
    identity=db.Column(db.String(20),nullable=False)
    verified = db.Column(db.Boolean, default=False, nullable=False)# ensure student that are verified
    post = db.relationship('Post', backref='users', passive_deletes=True) # Sets a relationship with Post table for 1 to Many relationship
    comments = db.relationship('Replies', backref='users', passive_deletes=True) 
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_removed = db.Column(db.Boolean, default=False)
    original_identity = db.Column(db.String(50))

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
        if self.email.endswith("@admin.mmu.edu.my"):
            self.is_admin = True
            return "admin"
       
    def has_helpful_feedback(self, post_id):
        feedback = Feedback.query.filter_by(
            reviewer=self.username,  
            post_id=post_id,
            is_helpful=True
        ).first()
        return feedback is not None
    
    def has_not_helpful_feedback(self, post_id):
        feedback = Feedback.query.filter_by(
            reviewer=self.username,  
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
    comments = db.relationship('Replies', backref='post', cascade="all, delete-orphan")
    images=db.relationship('Image', backref='post', cascade="all, delete-orphan", passive_deletes=True)
    helpful_count = db.Column(db.Integer, default=0) 
    not_helpful_count = db.Column(db.Integer, default=0)    
    item_id = db.Column(db.Integer, db.ForeignKey('item.id', ondelete="CASCADE"))
    is_removed = db.Column(db.Boolean, default=False)
    
    @property
    def total_feedback_count(self):
        return self.helpful_count + self.not_helpful_count

class Replies(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), db.ForeignKey('users.username', ondelete="CASCADE"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete="CASCADE"), nullable=False)
    is_removed = db.Column(db.Boolean, default=False)
    
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
    is_approved = db.Column(db.Boolean, default=False)
    submitted_by = db.Column(db.String(100), db.ForeignKey('users.username', ondelete='SET NULL'))
    images=db.relationship('Item_Image', backref='item', cascade="all, delete-orphan", passive_deletes=True)
    tags = db.relationship('Tag', secondary=item_tags, backref=db.backref('items', lazy='dynamic'))
    posts = db.relationship('Post', backref='item', cascade="all, delete-orphan")

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reviewer = db.Column(db.String(100), db.ForeignKey('users.username', ondelete="CASCADE"), nullable=False) 
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    is_helpful = db.Column(db.Boolean, nullable=False)
    
    # Relationship to Users via username
    user = db.relationship('Users', backref='feedbacks', foreign_keys=[reviewer])
    
    __table_args__ = (
        db.UniqueConstraint('reviewer', 'post_id', name='_user_post_uc'),
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
            'suck', 'nigga', 'fucking', 'ass', 'cibai'
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
     # Query all approved items with their images, tags, and non-removed posts count
    review_item = Item.query.options(
        db.joinedload(Item.images),  # Load all images
        db.joinedload(Item.tags),   # Load all tags
        db.joinedload(Item.posts)   # Load posts for counting
    ).filter_by(is_approved=True).all()


    if "user" not in session:
        flash("You aren't logged in. Please login or signup to see the reviews.", "danger")
        return render_template("intro.html")
      
    return render_template("home.html", items=review_item)

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
      
        pattern=r'^[a-zA-Z\.]+@(student\.mmu\.edu\.my|mmu\.edu\.my|admin\.mmu\.edu\.my)$'

        if not re.match(pattern, email):
            flash("Please use a valid MMU email address", "danger")
            return redirect(url_for("signup"))

        if actual_password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("signup"))

        existing_user = Users.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists", "danger")
            return redirect(url_for("signup"))

        existing_email = Users.query.filter_by(email=email).first()
        if existing_email:
            flash("Email already registered", "danger")
            return redirect(url_for("signup"))
      
        try:
            user = Users(
                email=email.lower(),
                username=username,
                password=generate_password_hash(actual_password,method="pbkdf2:sha256")
                )
            
            user.identity = user.get_identity()  # Force identity update

            if user.identity == "student":
                user.verified = False  # Students need verification
                token = generate_token(email)
                verify_url = url_for("verify_email", token=token, _external=True)
                send_verification_email(email, verify_url)
                flash("Please check your email for verfication", category='info')
            else:
                user.verified = True  # Auto-verify lecturers and admins

            db.session.add(user)
            db.session.commit()

            return redirect(url_for("login"))
      
            
        except Exception as e:
            db.session.rollback()
            flash("Error while saving to database: " + str(e), "danger")
            return redirect(url_for("signup"))

    return render_template("Signup.html")

@app.route("/verify/<token>")
def verify_email(token):
    try:
        email = confirm_token(token)
        if not email:
            flash("Invalid or expired verification link", "danger")
            return redirect(url_for("signup"))
        
        email = email.lower()
        user = Users.query.filter_by(email=email).first()
        if not user:
            flash("User not found", "danger")
            return redirect(url_for("signup"))
        
        if user.verified:
            flash("Account already verified", "info")
        else:
            user.verified = True
            db.session.commit()
            flash("Your account has been verified. You can now log in.", "success")
        
        return redirect(url_for("login"))  # Always redirect after verification
    
    except Exception as e:
        flash("Verification failed: " + str(e), "danger")
        return redirect(url_for("signup"))
    
@app.route("/request_reset", methods=["GET", "POST"])
def request_reset():
    if request.method == "POST":
      email=request.form.get("request_email")

      user=Users.query.filter_by(email=email.lower()).first()

      if user:
          
          token=generate_token(email)

          reset_url=url_for('reset_token',token=token,_external=True)

          send_reset_email(user.email, reset_url)

          flash('An email has been sent to reset your password.', 'info')

          return redirect(url_for('login')) 
        
      else:
            flash('No account found with that email address.', 'warning')

    return render_template("request_reset.html")

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_token(token):
    try:
        email=confirm_token(token)
    except:
        flash('The reset link is invalid or has expired.', 'warning')
        return redirect(url_for('request_reset'))
    
    user=Users.query.filter_by(email=email.lower()).first()

    if not user:
        flash('Invalid user.', 'warning')
        return redirect(url_for("request_reset"))
    
    if request.method == "POST":

        new_password = request.form.get('new_password')
        confirm_password=request.form.get('confirm_password')

        if not new_password or not confirm_password:
            flash('Both fields are required.', 'warning')
            return redirect(url_for("reset_token",token=token)) 

        if new_password != confirm_password:
            flash('Passwords do not match.', 'warning')
            return redirect(url_for("reset_token",token=token))   
        
        user.password = generate_password_hash(new_password)
        db.session.commit()

        flash('Your password has been updated! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html',token=token)


@app.route("/login",methods=["GET","POST"])
def login():
   
   if request.method == "POST":
      username=request.form["username"]
      password=request.form["password"]

      found_user = Users.query.filter_by(username=username).first()

      if found_user:
         if found_user.is_removed:
                flash("This account has been deactivated.", "danger")
                return redirect(url_for('login'))
         
         if check_password_hash(found_user.password,password):
            if not found_user.verified:
                flash("Your account is not yet verified. Please check your email for verification link.", "warning")
                return redirect(url_for("login"))
            else:
              session["user"]=found_user.username
              session["user_id"] = found_user.id
              session['identity'] = found_user.identity
              flash("Login Successful","success")
              return redirect(url_for("home"))
         else:
            flash("Incorrect password","danger")
      else:
         flash("Users does not exist","danger")
         return redirect(url_for("login"))
   return render_template("Login.html")

@app.context_processor
def inject_current_user():
    # Get username from session
    username = session.get('user')
    
    # If user is logged in, get their full user object
    if username:
        current_user = Users.query.filter_by(username=username).first()
        return {'current_user': current_user}
    return {'current_user': None}

@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("user_id", None)
    session.pop("identity", None)
    flash("You have been logged out.", "success")
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

#create default tags
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
    # Check if user is logged in
    if "user" not in session:
        flash("Please login to create a post", category="danger")
        return redirect(url_for("login"))

    # Get user and item
    username = session["user"]
    user = Users.query.filter_by(username=username).first()
    item = Item.query.get_or_404(item_id)  # This will automatically 404 if item doesn't exist
    
    if not user:
        flash("User not found", category="danger")
        return redirect(url_for("login"))
    
    if user.identity == "admin":
        flash('Admins are not allowed to create posts', category='danger')
        return redirect(url_for('view_item', item_id=item.id))
    
    # Check if user is lecturer and item has lecturer tag
    lecturer_tag = Tag.query.filter_by(name="Lecturer").first()
    if user.identity == "lecturer" and lecturer_tag in item.tags:
        flash("Lecturers are not allowed to create posts on lecturer tagged items", category="danger")
        return redirect(url_for('view_item', item_id=item.id))
    
    if request.method == "POST":
        text = request.form.get('text', '').strip()
        ratings = request.form.get('ratings')
        upload_files = request.files.getlist('picture')

        # Validation
        if not text:
            flash("Post cannot be empty", category='danger')
        elif not ratings:
            flash("Select a rating", category="danger")
        elif profanity_filter.contains_profanity(text):
            flash("Your comment contains inappropriate language and cannot be posted", category="danger")
        else:
            # Create post
            post = Post(
                text=text,
                author=username,
                ratings=int(ratings),
                item_id=item.id
            )
            db.session.add(post)
            
            try:
                db.session.flush()  # Get the post ID
                
                # Handle file uploads
                for file in upload_files:
                    if file.filename:  # Only process if file was actually uploaded
                        filename = secure_filename(file.filename)
                        file_ext = os.path.splitext(filename)[1].lower()
                        
                        if file_ext in ['.jpg', '.jpeg', '.png']:
                            unique_filename = f"{uuid.uuid4().hex}_{filename}"
                            file_path = os.path.join(app.config['POST_IMAGE_FOLDER'], unique_filename)
                            
                            file.save(file_path)
                            image = Image(filename=unique_filename, post_id=post.id)
                            db.session.add(image)
                
                db.session.commit()
                flash('Post created!', category='success')
                return redirect(url_for('view_item', item_id=item.id))
            
            except Exception as e:
                db.session.rollback()
                flash(f"Error creating post: {str(e)}", category='danger')

    # For GET requests or failed POSTs
    return render_template("create_post.html", item=item, text=request.form.get('text', ''))
                

@app.route("/delete-post/<int:id>", methods=['GET','POST'])
def delete_post(id):
    item_id = request.args.get('item_id', type=int)
    post = Post.query.filter_by(id=id).first()
    comment = Replies.query.filter_by(id=post.id).first()
    
    if not post:
        flash("Post doesn't exist", category="danger")
    elif session.get("user") != post.author:
        flash("You don't have permission to delete this post.", category="danger")
    else:
        post.ratings = 0
        post.is_removed = True

        for image in post.images:
            try:
                image_path = os.path.join(POST_IMAGE_FOLDER, image.filename)
                if os.path.exists(image_path):
                    os.remove(image_path)  # Delete the file
            except Exception as e:
                flash(f"Failed to delete image {image.filename}: {e}")

        # First delete all comments associated with the post
        for reply in post.comments:
            reply.is_removed = True

        related_reports = Report.query.filter_by(
        reported_content_id=comment.id,
        content_type='comment'
        ).all()
        for report in related_reports:
            db.session.delete(report)

        db.session.commit()
        flash("Post and its comments have been removed", category="success")

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
                return render_template('edit_post.html', post=post)
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
    username = session.get("user")
    user = Users.query.filter_by(username=username).first()
    comment = Replies.query.filter_by(id=comment_id).first()

    if not comment:
        flash("Comment doesn't exist", category="danger")
        return redirect(url_for('view_item', item_id=item_id))  # Exit early if comment is missing
    
    item_id = comment.post.item_id

    if session.get("user") != comment.author and session.get("user") != comment.post.author:
        flash("You don't have permission to delete this comment", category="danger")
        return redirect(url_for('view_item', item_id=item_id))
    
    comment.is_removed = True

    related_reports = Report.query.filter_by(
        reported_content_id=comment.id,
        content_type='comment'
    ).all()
        
    for report in related_reports:
        db.session.delete(report)
        
    flash("Comment deleted", category="success")
    db.session.delete(comment)
    db.session.commit()

    # Redirect logic
    referrer = request.referrer
    if referrer and '/profile/' in referrer:
        profile_username = referrer.split('/profile/')[-1].split('?')[0]
        return redirect(url_for('profile', username=profile_username))

    return redirect(url_for('view_item', item_id=item_id))


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
    items_query = Item.query.filter_by(is_approved=True)

    print("RAW form data:", request.form)

    # Initialize variables
    search_term = request.args.get('searched', '') if request.method == 'GET' else form.searched.data
    item_filter = request.args.get('item_filter', '') if request.method == 'GET' else form.item_filter.data

    # Build query for items
    items_query = Item.query
    
    # Apply search term filter
    if search_term:
        items_query = items_query.filter(
            db.or_(
                Item.name.ilike(f'%{search_term}%'),
                Item.description.ilike(f'%{search_term}%')
            )
        )
    
    # Apply item name filter
    if item_filter:
        items_query = items_query.filter(Item.name.ilike(f'%{item_filter}%'))

    # Get the results
    items = items_query.order_by(Item.name).all()
    
    return render_template('search.html', 
                        form=form, 
                        searched=search_term, 
                        items=items,
                        all_tags=all_tags,
                        selected_tags=selected_tags,
                        item_filter=item_filter)

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
    
    username = session["user"]  # Get username directly from session
    post = Post.query.get_or_404(post_id)
    
    # Check if user already gave feedback 
    existing_feedback = Feedback.query.filter_by(
        reviewer=username,
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
            feedback = Feedback(reviewer=username, post_id=post_id, is_helpful=True)
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
            feedback = Feedback(author=username, post_id=post_id, is_helpful=False)
            db.session.add(feedback)
    
    db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route("/additem", methods=["GET", "POST"])
def add_item():
    if 'user' not in session:
        flash("Please login to add items", "danger")
        return redirect(url_for('login'))
    
    user = Users.query.filter_by(username=session['user']).first()
    if not user:
        flash("User not found", "danger")
        return redirect(url_for('login'))
    
    create_tags()
    default_tags = Tag.query.filter_by(is_default=True).all()

    if request.method == "POST":
        name = request.form.get("name")
        selected_default_tags = request.form.getlist('default_tags')
        custom_tags = request.form.get('custom_tags',' ').strip()
        description = request.form.get("description")
        review_pic = request.files.getlist('review_picture')

        if not (name and description):
            flash("Please enter all required fields", "danger")
            return redirect(url_for('add_item'))
        
        # Validate at least one image was uploaded
        if not review_pic or any(file.filename == '' for file in review_pic):
           flash("Please upload at least one image", "danger")
           return redirect(url_for('add_item'))
        
        existing_item = Item.query.filter(db.func.lower(Item.name) == name.lower(),Item.is_approved == True ).first()  # Only check against approved items

        if existing_item:
            flash("An item with this name already exists", "danger")
            return redirect(url_for('add_item'))
        
        try:
            new_item = Item(
                name=name,
                description=description,
                submitted_by=user.username,
                is_approved=user.is_admin  # Auto-approve if admin adds
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

            if user.is_admin:
                flash("Item added successfully!", "success")
            else:
                flash("Item submitted for admin approval", "success")
            
            return redirect(url_for('home'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {str(e)}", "error")
            return redirect(url_for('home'))
    
    return render_template("add_item.html", default_tags=default_tags)

@app.route("/viewitem/<int:item_id>",methods=["GET", "POST"])
def view_item(item_id):
    item = Item.query.options(
        db.joinedload(Item.images),
        db.joinedload(Item.posts).joinedload(Post.users),
        db.joinedload(Item.posts).joinedload(Post.comments).joinedload(Replies.users)
    ).filter_by(id=item_id, is_approved=True).first_or_404()
    
    user = Users.query.get(session.get('user_id'))
    user_identity = user.identity

    return render_template('view_item.html', item=item,user_identity=user_identity)

@app.route("/edititem/<int:item_id>",methods=["GET", "POST"])
def edit_item(item_id):
    item=Item.query.get_or_404(item_id)

    default_tags = Tag.query.filter_by(is_default=True).all()

    # Get tags already associated with this item
    item_tags = item.tags
    item_tag_ids = {tag.id for tag in item_tags}  # Using set for faster lookup
    
    # Separate custom tags (non-default ones)
    custom_tags = [tag.name for tag in item_tags if not tag.is_default]
    custom_tags_str = ", ".join(custom_tags)

    if not item:
        flash("Item not found")
        return redirect(url_for('add_item',item_id=item_id))
    
    if request.method == "POST":
        # Get form data
        name = request.form.get("name")
        description = request.form.get("description")
        upload_image = request.files.getlist("picture")
        delete_image=request.form.getlist("delete_images")

        # Handle default tags
        selected_tag_ids = request.form.getlist("default_tags")  # getlist for multiple values
        selected_tag_ids = [int(id) for id in selected_tag_ids]

        # Handle custom tags
        custom_tags_input = request.form.get("custom_tags", "").strip()
        new_custom_tags = [t.strip() for t in custom_tags_input.split(",") if t.strip()]
        
        try:
            
            item.name = name
            item.description = description
            
            # Update default tags
            current_tag_ids = {tag.id for tag in item.tags}
            
            # Tags to remove
            tags_to_remove = current_tag_ids - set(selected_tag_ids)
            for tag_id in tags_to_remove:
                tag = Tag.query.get(tag_id)
                if tag and tag.is_default:  # Only remove default tags
                    item.tags.remove(tag)
            
            # Tags to add
            tags_to_add = set(selected_tag_ids) - current_tag_ids
            for tag_id in tags_to_add:
                tag = Tag.query.get(tag_id)
                if tag:
                    item.tags.append(tag)
            
            # Handle custom tags
            existing_custom_tags = {tag.name.lower(): tag for tag in item.tags if not tag.is_default}
            
            # Remove custom tags not in new input
            for tag_name, tag in existing_custom_tags.items():
                if tag_name not in [t.lower() for t in new_custom_tags]:
                    item.tags.remove(tag)
            
            # Add new custom tags
            for tag_name in new_custom_tags:
                if tag_name.lower() not in existing_custom_tags:
                    # Find or create the tag
                    tag = Tag.query.filter(Tag.name.ilike(tag_name)).first()
                    if not tag:
                        tag = Tag(name=tag_name, is_default=False)
                        db.session.add(tag)
                    item.tags.append(tag)

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
                         file_path = os.path.join(app.config['ITEM_IMAGE_FOLDER'], filename)

                         try:
                              file.save(file_path)
                              # Create image record in database
                              image = Item_Image(filename=filename, item_id=item_id)
                              db.session.add(image)
                         except Exception as e:
                           flash(f"Error saving image: {str(e)}", category='danger')

            # Handle image deletions
            if delete_image:
               for image_id in delete_image:
                image = Item_Image.query.get(int(image_id))
                if image and image.item_id == item.id:  
                    # Delete file from filesystem
                    filepath = os.path.join(app.config['ITEM_IMAGE_FOLDER'], image.filename)
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    # Delete from database
                    db.session.delete(image)

            db.session.commit()
            flash("Item updated successfully!", 'success')
            return redirect(url_for('view_item', item_id=item.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating item: {str(e)}", "error")

    return render_template("edit_item.html",item=item,default_tags=default_tags,item_tag_ids=item_tag_ids,custom_tags_str=custom_tags_str)

@app.route("/deleteitem/<int:item_id>", methods=["GET", "POST"])
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)

    try:
        # Delete item images
        for image in item.images:
            image_path = os.path.join(app.config['ITEM_IMAGE_FOLDER'], image.filename)
            try:
                if os.path.exists(image_path):
                    os.remove(image_path)
            except Exception as e:
                flash(f"Failed to delete image {image.filename}: {str(e)}")

        # Delete associated posts, post images, feedback, and reports
        for post in item.posts:
            # Delete feedback
            Feedback.query.filter_by(post_id=post.id).delete()

            # Delete post images
            for image in post.images:
                try:
                    post_image_path = os.path.join(app.config['POST_IMAGE_FOLDER'], image.filename)
                    if os.path.exists(post_image_path):
                        os.remove(post_image_path)
                except Exception as e:
                    flash(f"Failed to delete post image {image.filename}: {str(e)}", "warning")

            # Delete reports related to this post
            Report.query.filter_by(content_type='post', reported_content_id=post.id).delete()

            # Delete reports related to comments under this post (if applicable)
            for comment in post.comments:
                Report.query.filter_by(content_type='comment', reported_content_id=comment.id).delete()

        # Delete the item (will cascade-delete posts, images, comments if relationships are set with cascade)
        db.session.delete(item)
        db.session.commit()

        flash("Item and all associated content deleted successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting item: {str(e)}", "danger")

    return redirect(url_for('home'))

@app.route('/reported/post/<int:post_id>', methods = ['GET', 'POST'])
def report_post(post_id):
    if 'user' not in session:
        flash("Please login to report content", category="danger")
        return redirect(url_for('login'))
    
    # To find the post
    post = Post.query.get_or_404(post_id)

    if request.method == 'POST':
        reason = request.form.get('reason')
        details = request.form.get('details')

        if not reason: 
            flash("Please select a reason for reporting", category="danger")
        else:
            #Checks if user already reported this post
            existing_report = Report.query.filter_by(
                
                reporter_id=session['user_id'], # Current logged in session
                reported_content_id=post_id, # Get reported post id 
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

@app.route('/admin')
def admin_dashboard():
    if 'user' not in session:
        flash("Please login to access admin panel", category="danger")
        return redirect(url_for('login'))

    user = Users.query.filter_by(username=session['user']).first()
    if not user or not user.is_admin:
        flash("You don't have permission to access this page", category="danger")
        return redirect(url_for('home'))
    
    # Display total users, reports, and posts
    total_users = Users.query.filter_by(is_removed=False).count()
    total_posts = Post.query.count()
    total_reports = Report.query.count()
    pending_items_count = Item.query.filter_by(is_approved=False).count()

    hidden_posts_count = Post.query.filter_by(is_removed=True).count()
    hidden_comments_count = Replies.query.filter_by(is_removed=True).count()
    hidden_content_count = hidden_posts_count + hidden_comments_count

    recent_reports = Report.query.order_by(Report.id.asc()).limit(3).all()
    pending_items = Item.query.filter_by(is_approved=False).order_by(Item.id.asc()).limit(3).all()

    return render_template('admin_dashboard.html', 
                         total_users=total_users,
                         total_posts=total_posts,
                         total_reports=total_reports,
                         pending_items_count=pending_items_count,
                         recent_reports=recent_reports,
                         pending_items=pending_items,
                         hidden_comments_count=hidden_comments_count)

@app.route('/admin/users')
def admin_users():
    if 'user' not in session:
        flash("Please login to access admin panel", category="danger")
        return redirect(url_for('login'))

    user = Users.query.filter_by(username=session['user']).first()
    if not user or not user.is_admin:
        flash("You don't have permission to access this page", category="danger")
        return redirect(url_for('home'))
    
    users = Users.query.order_by(Users.id.asc()).all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/reports')
def admin_reports():
    if 'user' not in session:
        flash("Please login to access admin panel", category="danger")
        return redirect(url_for('login'))

    user = Users.query.filter_by(username=session['user']).first()
    if not user or not user.is_admin:
        flash("You don't have permission to access this page", category="danger")
        return redirect(url_for('home'))
    
    reports = Report.query.order_by(Report.id.desc()).all()
    return render_template('admin_reports.html', reports=reports)
        
import re

def get_identity_from_email(email):
    if email.endswith('@student.mmu.edu.my'):
        return 'student'
    elif email.endswith('@mmu.edu.my'):
        return 'staff'
    elif email.endswith('@admin.mmu.edu.my'):
        return 'staff'  # or 'admin', depending on your logic
    else:
        return 'user'  # fallback identity
    
def get_identity_from_email(email):
    if email.endswith('@student.mmu.edu.my'):
        return 'student'
    elif email.endswith('@mmu.edu.my'):
        return 'lecturer'
    elif email.endswith('@admin.mmu.edu.my'):
        return 'staff'  # or 'admin', depending on your logic

@app.route('/admin/toggle-admin/<int:user_id>')
def toggle_admin(user_id):
    if 'user' not in session:
        flash("Please login to access admin panel", category="danger")
        return redirect(url_for('login'))

    current_user = Users.query.filter_by(username=session['user']).first()
    if not current_user or not current_user.is_admin:
        flash("You don't have permission to access this page", category="danger")
        return redirect(url_for('home'))

    user = Users.query.get_or_404(user_id)
    if user_id == current_user.id:
        flash("You cannot modify your own admin status", category="warning")
        return redirect(url_for('home'))

    if not user.is_admin:
        user.identity = "admin"
        user.is_admin = True
    else:
        user.identity = get_identity_from_email(user.email)
        user.is_admin = False

    db.session.commit()
    status = "granted" if user.is_admin else "revoked"
    flash(f"Admin privileges {status} for {user.username}", category='success')
    return redirect(url_for('admin_users'))


@app.route('/admin/delete-user/<int:user_id>')
def admin_delete_user(user_id):
    if 'user' not in session:
        flash("Please login to access admin panel", category="danger")
        return redirect(url_for('login'))

    current_user = Users.query.filter_by(username=session['user']).first()
    if not current_user or not current_user.is_admin:
        flash("You don't have permission to access this page", category="danger")
        return redirect(url_for('home'))

    user = Users.query.get_or_404(user_id)
    if user_id == current_user.id:
        flash("You cannot delete yourself", category="danger")
    else:
        # Soft delete implementation
        user.is_removed = True
        db.session.commit()

        if 'user_id' in session and session['user_id'] == user_id:
            session.pop('user', None)
            session.pop('user_id', None)
            session.pop('identity', None)

        flash(f"User {user.username} has been deactivated", "success")

    return redirect(url_for('admin_users'))

@app.route('/admin/hide-content/<content_type>/<int:content_id>')
def admin_hide_content(content_type, content_id):
    if 'user' not in session:
        flash("Please login to access admin panel", category="danger")
        return redirect(url_for('login'))

    current_user = Users.query.filter_by(username=session['user']).first()
    if not current_user or not current_user.is_admin:
        flash("You don't have permission to access this page", category="danger")
        return redirect(url_for('home'))
    
    # Soft delete logic
    if content_type == 'post':
        content = Post.query.get_or_404(content_id)
        content.is_removed = True
        for comment in content.comments:
            comment.is_removed = True  # Optional: hide associated comments

    elif content_type == 'comment':
        content = Replies.query.get_or_404(content_id)
        content.is_removed = True

    else:
        flash("Invalid content type", category="danger")
        return redirect(url_for("admin_dashboard"))
    
    db.session.commit()

    # Hard delete associated reports
    Report.query.filter_by(
        content_type=content_type,
        reported_content_id=content_id
    ).delete()
    db.session.commit()

    flash("Content has been marked as [deleted] and reports removed", category='success')
    return redirect(url_for("admin_dashboard"))

@app.route('/admin/dismiss-report/<int:report_id>')
def admin_dismiss_report(report_id):
    if 'user' not in session:
        flash("Please login to access admin panel", category="danger")
        return redirect(url_for('login'))

    current_user = Users.query.filter_by(username=session['user']).first()
    if not current_user or not current_user.is_admin:
        flash("You don't have permission to access this page", category="danger")
        return redirect(url_for('home'))

    report = Report.query.get_or_404(report_id)
    db.session.delete(report)
    db.session.commit()

    flash("Report has been dismissed", "info")
    return redirect(url_for('admin_reports'))  # or wherever you want to return

@app.route('/admin/pending-items')
def pending_items():
    if 'user' not in session:
        flash("Please login to access admin panel", "danger")
        return redirect(url_for('login'))

    user = Users.query.filter_by(username=session['user']).first()
    if not user or not user.is_admin:
        flash("You don't have permission to access this page", "danger")
        return redirect(url_for('home'))
    
    pending_items = Item.query.filter_by(is_approved=False).all()
    return render_template('admin_pending_items.html', items=pending_items)

@app.route('/admin/approve-item/<int:item_id>')
def approve_item(item_id):
    if 'user' not in session:
        flash("Please login to access admin panel", "danger")
        return redirect(url_for('login'))

    user = Users.query.filter_by(username=session['user']).first()
    if not user or not user.is_admin:
        flash("You don't have permission to access this page", "danger")
        return redirect(url_for('home'))
    
    item = Item.query.get_or_404(item_id)
    item.is_approved = True
    db.session.commit()
    
    flash("Item approved and published", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject-item/<int:item_id>')
def reject_item(item_id):
    if 'user' not in session:
        flash("Please login to access admin panel", "danger")
        return redirect(url_for('login'))

    user = Users.query.filter_by(username=session['user']).first()
    if not user or not user.is_admin:
        flash("You don't have permission to access this page", "danger")
        return redirect(url_for('home'))
    
    item = Item.query.get_or_404(item_id)
    
    # Delete associated images first
    for image in item.images:
        try:
            os.remove(os.path.join(app.config['ITEM_IMAGE_FOLDER'], image.filename))
        except:
            pass
    
    db.session.delete(item)
    db.session.commit()
    
    flash("Item rejected and deleted", "success")
    return redirect(url_for('admin_dashboard'))

@app.before_request
def check_account_status():
    if 'user' in session:
        user = Users.query.filter_by(username=session['user']).first()
        if not user or user.is_removed:
            # Clear session and force logout
            session.pop("user", None)
            session.pop("user_id", None)
            session.pop("identity", None)
            flash("Your account has been deactivated or removed.", "danger")
            return redirect(url_for("login"))

if __name__ == '__main__':  
   with app.app_context():  # Needed for DB operations outside a request
        db.create_all() 
   app.run(debug=True)
