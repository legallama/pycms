from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length

from ..models.cms import PublishStatus


class PageForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=255)])
    slug = StringField("Slug", validators=[DataRequired(), Length(max=200)])
    body_html = TextAreaField("Body", default="")
    status = SelectField(
        "Status",
        choices=[(PublishStatus.DRAFT.value, "Draft"), (PublishStatus.PUBLISHED.value, "Published")],
        validators=[DataRequired()],
        default=PublishStatus.DRAFT.value,
    )
    layout = SelectField("Template Layout", choices=[], default="default")
    menu_id = SelectField("Assigned Menu", coerce=int, choices=[])


class PostForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=255)])
    slug = StringField("Slug", validators=[DataRequired(), Length(max=200)])
    body_html = TextAreaField("Body", default="")
    status = SelectField(
        "Status",
        choices=[(PublishStatus.DRAFT.value, "Draft"), (PublishStatus.PUBLISHED.value, "Published")],
        validators=[DataRequired()],
        default=PublishStatus.DRAFT.value,
    )
