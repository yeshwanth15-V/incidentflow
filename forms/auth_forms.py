from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from models.user import User

class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Sign In")

class CreateUserForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    full_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField("Email Address", validators=[DataRequired(), Email(check_deliverability=False), Length(max=120)])
    role = SelectField("Role", choices=[("Support Agent", "Support Agent"), ("Admin", "Admin")], default="Support Agent")
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=128)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")])
    submit = SubmitField("Create Team Member")
    
    def validate_username(self, field):
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError("This username is already taken. Please choose another.")
            
    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("An account with this email address already exists.")

class EditUserForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField("Email Address", validators=[DataRequired(), Email(check_deliverability=False), Length(max=120)])
    role = SelectField("Role", choices=[("Support Agent", "Support Agent"), ("Admin", "Admin")])
    is_active_account = BooleanField("Active Account")
    new_password = PasswordField("New Password (leave blank to keep current)", validators=[Optional(), Length(min=6, max=128)])
    submit = SubmitField("Update Team Member")
    
    def __init__(self, original_user=None, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        self.original_user = original_user
        
    def validate_email(self, field):
        if self.original_user and field.data.strip().lower() != self.original_user.email.lower():
            if User.query.filter_by(email=field.data.strip().lower()).first():
                raise ValidationError("An account with this email address already exists.")
