from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    consumer_number = db.Column(db.String(20), unique=True, nullable=True)
    address = db.Column(db.Text, nullable=True)
    district = db.Column(db.String(80), nullable=True)
    state = db.Column(db.String(80), default='Bihar')
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    role = db.Column(db.String(30), default='consumer')  # consumer, super_admin, operator, complaint_officer, field_staff
    department = db.Column(db.String(120), nullable=True)
    profile_pic = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    complaints = db.relationship('Complaint', backref='user', lazy='dynamic', foreign_keys='Complaint.user_id')
    replies = db.relationship('Reply', backref='author', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    assigned_complaints = db.relationship('Complaint', foreign_keys='Complaint.assigned_to', backref='assignee', lazy='dynamic')
    complaint_logs = db.relationship('ComplaintLog', backref='actor', lazy='dynamic')
    audit_logs = db.relationship('AdminAuditLog', backref='actor', lazy='dynamic')

    STAFF_ROLES = {'super_admin', 'operator', 'complaint_officer', 'field_staff'}

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_staff(self):
        return self.is_admin or self.role in self.STAFF_ROLES

    @property
    def display_role(self):
        return (self.role or 'consumer').replace('_', ' ').title()

    def __repr__(self):
        return f'<User {self.email}>'


class Complaint(db.Model):
    __tablename__ = 'complaints'

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    sub_category = db.Column(db.String(80), nullable=True)
    priority = db.Column(db.String(20), default='medium')
    status = db.Column(db.String(30), default='pending')
    attachment = db.Column(db.String(200), nullable=True)
    address = db.Column(db.Text, nullable=True)
    district = db.Column(db.String(80), nullable=True)
    meter_number = db.Column(db.String(30), nullable=True)
    consumer_number = db.Column(db.String(20), nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    department = db.Column(db.String(120), nullable=True)
    field_unit = db.Column(db.String(120), nullable=True)
    expected_resolution_date = db.Column(db.DateTime, nullable=True)
    first_review_at = db.Column(db.DateTime, nullable=True)
    escalated_at = db.Column(db.DateTime, nullable=True)
    resolution_summary = db.Column(db.Text, nullable=True)
    admin_note = db.Column(db.Text, nullable=True)
    internal_remarks = db.Column(db.Text, nullable=True)
    reopen_count = db.Column(db.Integer, default=0)
    is_closed_by_user = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    replies = db.relationship('Reply', backref='complaint', lazy='dynamic', cascade='all, delete-orphan')
    attachments = db.relationship('ComplaintAttachment', backref='complaint', lazy='dynamic', cascade='all, delete-orphan')
    logs = db.relationship('ComplaintLog', backref='complaint', lazy='dynamic', cascade='all, delete-orphan')
    rating = db.relationship('SatisfactionRating', backref='complaint', uselist=False, cascade='all, delete-orphan')

    CATEGORIES = [
        ('power_outage', 'Power Outage'),
        ('billing', 'Billing Issue'),
        ('meter_fault', 'Meter Fault'),
        ('new_connection', 'New Connection'),
        ('low_voltage', 'Low Voltage'),
        ('transformer', 'Transformer Issue'),
        ('streetlight', 'Street Light'),
        ('service_request', 'Service Request'),
        ('safety', 'Safety Hazard'),
        ('other', 'Other'),
    ]

    PRIORITIES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')]
    STATUSES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('reopened', 'Reopened'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
        ('escalated', 'Escalated'),
    ]

    def get_category_label(self):
        return dict(self.CATEGORIES).get(self.category, self.category)

    def get_priority_label(self):
        return dict(self.PRIORITIES).get(self.priority, self.priority)

    def get_status_label(self):
        return dict(self.STATUSES).get(self.status, self.status)

    @property
    def can_be_edited_by_user(self):
        return self.status == 'pending' and self.first_review_at is None

    @property
    def is_overdue(self):
        return bool(self.expected_resolution_date and self.status not in {'resolved', 'closed', 'rejected'} and datetime.utcnow() > self.expected_resolution_date)

    @property
    def current_step(self):
        if self.status in {'pending'}:
            return 1
        if self.status in {'under_review', 'assigned'}:
            return 2
        if self.status in {'in_progress', 'escalated', 'reopened'}:
            return 3
        if self.status in {'resolved'}:
            return 4
        return 5

    @property
    def progress_steps(self):
        return [
            ('Filed', 1),
            ('Review', 2),
            ('Action', 3),
            ('Resolved', 4),
            ('Closed', 5),
        ]

    def default_eta(self):
        mapping = {'urgent': 1, 'high': 2, 'medium': 4, 'low': 7}
        return self.created_at + timedelta(days=mapping.get(self.priority, 4))

    def __repr__(self):
        return f'<Complaint {self.complaint_id}>'


class ComplaintAttachment(db.Model):
    __tablename__ = 'complaint_attachments'

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class ComplaintLog(db.Model):
    __tablename__ = 'complaint_logs'

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    visible_to_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SatisfactionRating(db.Model):
    __tablename__ = 'satisfaction_ratings'

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    feedback = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Reply(db.Model):
    __tablename__ = 'replies'

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_admin_reply = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class OTP(db.Model):
    __tablename__ = 'otps'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    otp_code = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_used = db.Column(db.Boolean, default=False)


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    notif_type = db.Column(db.String(30), default='info')
    related_complaint = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AdminAuditLog(db.Model):
    __tablename__ = 'admin_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    details = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
