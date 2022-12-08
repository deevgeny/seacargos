from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField, validators


class LoginForm(FlaskForm):
    """User login form."""
    username = StringField("Username", validators=[validators.DataRequired()])
    password = PasswordField("Password",
                             validators=[validators.DataRequired()])
    submit = SubmitField("Log in")
