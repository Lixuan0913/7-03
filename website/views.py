from flask import Blueprint, render_template, request, flash

views = Blueprint("views", __name__)

@views.route("/")
@views.route("/home")
def home():
    return render_template("home.html")

@views.route("/create-post", methods=['GET', 'POST'])
def create_post():
    if request.method == "POST":
        text = request.form.get('text')

        if not text:
            flash("Post cannot be empty", category='error')
        else:
            flash('Post created!', category='success')

    return render_template("create_post.html")