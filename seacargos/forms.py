from flask_wtf import FlaskForm
from wtforms import (
    DateField,
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
    role = SelectField("Role", validators=[validators.DataRequired()])
    password = PasswordField("Password",
                             validators=[validators.DataRequired()])
    password_repeat = PasswordField("Repeat password",
                                    validators=[validators.DataRequired()])
    submit = SubmitField("Add")


class EditUserForm(FlaskForm):
    """Edit user form."""
    username = SelectField("Username", validators=[validators.DataRequired()])
    role = SelectField("Role", validators=[validators.optional()])
    password = PasswordField("Password",
                             validators=[validators.optional()])
    password_repeat = PasswordField("Repeat password",
                                    validators=[validators.optional()])
    submit = SubmitField("Submit")


class BlockUserForm(FlaskForm):
    """Block user form."""
    username = SelectField("Username", validators=[validators.DataRequired()])
    submit = SubmitField("Block")


class UnblockUserForm(BlockUserForm):
    """Unblock user form."""
    submit = SubmitField("Unblock")


class TrackingForm(FlaskForm):
    """Add new tracking record form."""
    booking = StringField("Booking or container No.",
                          validators=[validators.DataRequired()])
    ref_id = StringField("Ref Id", validators=[validators.optional()])
    requested_eta = DateField("Requested ETA",
                              validators=[validators.optional()])
    submit = SubmitField("Add")
