from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectMultipleField
from wtforms.validators import Optional

class SearchForm(FlaskForm):
    searched = StringField('Search', validators=[Optional()])
    tags = SelectMultipleField('Filter by Tags', choices=[], validators=[Optional()])
    item_filter = StringField('Filter by Item Name', validators=[Optional()])
    submit = SubmitField('Search')