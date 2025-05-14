from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import Optional

class SearchForm(FlaskForm):
    searched = StringField('Search', validators=[Optional()])
    item_filter = StringField('Filter by Item Name', validators=[Optional()])
    tag_search = StringField('Search Tags', validators=[Optional()])
    submit = SubmitField('Search')
