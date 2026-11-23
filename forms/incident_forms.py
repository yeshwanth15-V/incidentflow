from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

PRIORITY_CHOICES = [
    ("Critical", "Critical (4h SLA)"),
    ("High", "High (8h SLA)"),
    ("Medium", "Medium (24h SLA)"),
    ("Low", "Low (48h SLA)")
]

STATUS_CHOICES = [
    ("Open", "Open"),
    ("In Progress", "In Progress"),
    ("Resolved", "Resolved"),
    ("Closed", "Closed")
]

CATEGORY_CHOICES = [
    ("Software", "Software"),
    ("Hardware", "Hardware"),
    ("Network", "Network"),
    ("Security", "Security"),
    ("Database", "Database"),
    ("Infrastructure", "Infrastructure"),
    ("General", "General")
]

class IncidentCreateForm(FlaskForm):
    title = StringField("Incident Title", validators=[
        DataRequired(message="Title is required."),
        Length(min=3, max=150, message="Title must be between 3 and 150 characters.")
    ])
    description = TextAreaField("Description & Impact", validators=[
        DataRequired(message="Description is required.")
    ])
    priority = SelectField("Priority", choices=PRIORITY_CHOICES, default="Medium")
    category = SelectField("Category", choices=CATEGORY_CHOICES, default="General")
    assigned_user_id = SelectField("Assign To", coerce=int, validators=[Optional()])
    submit = SubmitField("Submit Incident")

class IncidentEditForm(FlaskForm):
    title = StringField("Incident Title", validators=[
        DataRequired(message="Title is required."),
        Length(min=3, max=150, message="Title must be between 3 and 150 characters.")
    ])
    description = TextAreaField("Description & Impact", validators=[
        DataRequired(message="Description is required.")
    ])
    priority = SelectField("Priority", choices=PRIORITY_CHOICES)
    status = SelectField("Status", choices=STATUS_CHOICES)
    category = SelectField("Category", choices=CATEGORY_CHOICES)
    assigned_user_id = SelectField("Assign To", coerce=int, validators=[Optional()])
    submit = SubmitField("Save Changes")

class IncidentStatusUpdateForm(FlaskForm):
    status = SelectField("New Status", choices=STATUS_CHOICES, validators=[DataRequired()])
    comment = TextAreaField("Activity Note / Resolution Comment", validators=[Optional()])
    submit = SubmitField("Update Status")
