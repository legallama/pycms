from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, Email, Length, Optional

from ..models.user import UserRole


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=256)])


class UserCreateForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    role = SelectField(
        "Role",
        choices=[(UserRole.ADMIN.value, "Admin"), (UserRole.EDITOR.value, "Editor"), (UserRole.AUTHOR.value, "Author")],
        validators=[DataRequired()],
    )
    is_active = BooleanField("Active", default=True)
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=256)])


class UserEditForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    role = SelectField(
        "Role",
        choices=[(UserRole.ADMIN.value, "Admin"), (UserRole.EDITOR.value, "Editor"), (UserRole.AUTHOR.value, "Author")],
        validators=[DataRequired()],
    )
    is_active = BooleanField("Active", default=True)
    password = PasswordField("New password (optional)", validators=[Optional(), Length(min=8, max=256)])

