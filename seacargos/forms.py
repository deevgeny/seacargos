from flask_wtf import FlaskForm
from wtforms import (
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    validators,
)


class LoginForm(FlaskForm):
    """User login form."""
    username = StringField("Username", validators=[validators.DataRequired()])
    password = PasswordField("Password",
                             validators=[validators.DataRequired()])
    submit = SubmitField("Log in")


class AddUserForm(FlaskForm):
    """Add new user form."""
    username = StringField("Username", validators=[validators.DataRequired()])
    role = SelectField("Role", validators=[validators.optional()])
    password = PasswordField("Password",
                             validators=[validators.DataRequired()])
    password_repeat = PasswordField("Password",
                                    validators=[validators.DataRequired()])
    submit = SubmitField("Add")
