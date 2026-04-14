import csv
import io
import os
import random
import secrets
import string
from datetime import datetime, timedelta
from functools import wraps

from flask import session, redirect, url_for, flash, current_app, request, abort
from flask_login import current_user
from flask_mail import Message
from extensions import mail, db
from models import OTP, Notification, ComplaintLog, AdminAuditLog


# ── ID Generators ────────────────────────────────────────────────────────────

def generate_complaint_id():
    year = datetime.utcnow().year
    suffix = ''.join(random.choices(string.digits, k=5))
    return f"CMP-{year}-{suffix}"


def generate_consumer_number():
    digits = ''.join(random.choices(string.digits, k=10))
    return f"BSPHCL-{digits}"


def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))


# ── CSRF ────────────────────────────────────────────────────────────────────

def get_csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_hex(16)
        session['_csrf_token'] = token
    return token


def validate_csrf_token():
    token = request.form.get('_csrf_token') or request.headers.get('X-CSRFToken')
    if not token or token != session.get('_csrf_token'):
        abort(400, description='Invalid security token.')


# ── File Helpers ─────────────────────────────────────────────────────────────

def allowed_file(filename):
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'pdf'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def save_uploaded_file(file, subfolder='complaints'):
    if not file or not getattr(file, 'filename', ''):
        return None
    if not allowed_file(file.filename):
        return None

    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024)
    try:
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(0)
    except Exception:
        size = 0
    if size and size > max_size:
        return None

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{''.join(random.choices(string.ascii_lowercase + string.digits, k=20))}.{ext}"
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, unique_name)
    file.save(filepath)
    return os.path.join(subfolder, unique_name)


# ── OTP Helpers ──────────────────────────────────────────────────────────────

def create_otp(email):
    OTP.query.filter_by(email=email, is_used=False).update({'is_used': True})
    db.session.commit()
    code = generate_otp()
    otp = OTP(email=email, otp_code=code)
    db.session.add(otp)
    db.session.commit()
    return code


def verify_otp(email, code):
    expiry = datetime.utcnow() - timedelta(minutes=current_app.config.get('OTP_EXPIRY_MINUTES', 10))
    otp = OTP.query.filter_by(email=email, otp_code=code, is_used=False).filter(OTP.created_at >= expiry).first()
    if otp:
        otp.is_used = True
        db.session.commit()
        return True
    return False


# ── Mail Helpers ─────────────────────────────────────────────────────────────

def _safe_send_message(msg):
    try:
        mail.send(msg)
        return True
    except Exception:
        return False


def send_otp_email(email, otp_code, name='User'):
    msg = Message(
        subject='BSPHCL Password Reset OTP',
        recipients=[email],
        html=f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
          <div style="background:#1d4ed8;padding:20px;color:#fff;"><h2 style="margin:0;font-size:22px;">BSPHCL Consumer Portal</h2></div>
          <div style="padding:24px;background:#fff;">
            <p>Dear <strong>{name}</strong>,</p>
            <p>Your one-time password for account recovery is:</p>
            <div style="padding:16px;border:1px solid #dbeafe;background:#eff6ff;border-radius:10px;text-align:center;font-size:32px;font-weight:700;letter-spacing:6px;color:#1d4ed8;">{otp_code}</div>
            <p style="color:#6b7280;font-size:13px;margin-top:16px;">This OTP is valid for 10 minutes.</p>
          </div>
        </div>
        """
    )
    return _safe_send_message(msg)


def send_status_email(email, complaint, name='Consumer'):
    msg = Message(
        subject=f'Complaint Status Update - {complaint.complaint_id}',
        recipients=[email],
        html=f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
          <div style="background:#1d4ed8;padding:20px;color:#fff;"><h2 style="margin:0;font-size:22px;">Complaint Status Update</h2></div>
          <div style="padding:24px;background:#fff;">
            <p>Dear <strong>{name}</strong>,</p>
            <p>Your complaint <strong>{complaint.complaint_id}</strong> is now marked as <strong>{complaint.get_status_label()}</strong>.</p>
            <p><strong>Subject:</strong> {complaint.subject}</p>
            <p><strong>Expected Resolution:</strong> {complaint.expected_resolution_date.strftime('%d %b %Y') if complaint.expected_resolution_date else 'To be updated'}</p>
            <p style="color:#6b7280;font-size:13px;">Please log in to the portal to view the latest timeline and remarks.</p>
          </div>
        </div>
        """
    )
    return _safe_send_message(msg)


def send_complaint_confirmation(email, complaint_id, subject, name='User'):
    msg = Message(
        subject=f'Complaint Registered - {complaint_id}',
        recipients=[email],
        html=f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
          <div style="background:#1d4ed8;padding:20px;color:#fff;"><h2 style="margin:0;font-size:22px;">Complaint Registration Acknowledgement</h2></div>
          <div style="padding:24px;background:#fff;">
            <p>Dear <strong>{name}</strong>,</p>
            <p>Your complaint has been registered successfully.</p>
            <p><strong>Complaint ID:</strong> {complaint_id}<br><strong>Subject:</strong> {subject}</p>
            <p style="color:#6b7280;font-size:13px;">Keep this complaint ID for future tracking.</p>
          </div>
        </div>
        """
    )
    return _safe_send_message(msg)


# ── Decorators ───────────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_staff:
            flash('Authorized staff access required.', 'danger')
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated_function


# ── Notification + Audit Helpers ─────────────────────────────────────────────

def create_notification(user_id, title, message, notif_type='info', related_complaint=None):
    notif = Notification(user_id=user_id, title=title, message=message, notif_type=notif_type, related_complaint=related_complaint)
    db.session.add(notif)
    db.session.commit()
    return notif


def log_complaint_action(complaint, action, message, user_id=None, visible_to_user=True):
    log = ComplaintLog(
        complaint_id=complaint.id,
        user_id=user_id,
        action=action,
        message=message,
        visible_to_user=visible_to_user,
    )
    db.session.add(log)
    db.session.commit()
    return log


def audit_admin_action(action, details, user_id=None):
    log = AdminAuditLog(user_id=user_id, action=action, details=details)
    db.session.add(log)
    db.session.commit()
    return log


# ── Export Helpers ───────────────────────────────────────────────────────────

def complaints_to_csv_bytes(complaints):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Complaint ID', 'Consumer Number', 'Subject', 'Category', 'Priority', 'Status', 'District', 'Department', 'Expected Resolution', 'Created At'])
    for c in complaints:
        writer.writerow([
            c.complaint_id, c.consumer_number, c.subject, c.get_category_label(), c.get_priority_label(),
            c.get_status_label(), c.district or '', c.department or '',
            c.expected_resolution_date.strftime('%Y-%m-%d') if c.expected_resolution_date else '',
            c.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    return output.getvalue().encode('utf-8')


# ── PDF Helpers ──────────────────────────────────────────────────────────────

def generate_complaint_pdf(complaint, user, mode='acknowledgement'):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=1.8*cm, bottomMargin=1.8*cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Title'], textColor=colors.HexColor('#1d4ed8'), fontSize=20, leading=24)
        heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], textColor=colors.HexColor('#111827'), spaceAfter=8)
        story = []

        title = 'Complaint Acknowledgement Slip' if mode == 'acknowledgement' else 'Complaint Resolution Report'
        story.append(Paragraph('BSPHCL Consumer Complaint Portal', title_style))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(title, heading_style))
        story.append(Spacer(1, 0.3*cm))

        data = [
            ['Complaint ID', complaint.complaint_id],
            ['Consumer Name', user.name],
            ['Consumer Number', complaint.consumer_number or user.consumer_number or 'N/A'],
            ['Category', complaint.get_category_label()],
            ['Priority', complaint.get_priority_label()],
            ['Status', complaint.get_status_label()],
            ['Department', complaint.department or 'Pending assignment'],
            ['Assigned Officer', complaint.assignee.name if complaint.assignee else 'Pending assignment'],
            ['Expected Resolution', complaint.expected_resolution_date.strftime('%d %b %Y') if complaint.expected_resolution_date else 'To be updated'],
            ['Filed On', complaint.created_at.strftime('%d %b %Y, %I:%M %p')],
        ]
        if mode == 'resolution':
            data.extend([
                ['Resolved On', complaint.resolved_at.strftime('%d %b %Y, %I:%M %p') if complaint.resolved_at else 'Not resolved'],
                ['Resolution Summary', complaint.resolution_summary or 'Not available'],
            ])

        table = Table(data, colWidths=[5*cm, 10.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eff6ff')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1d4ed8')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9.5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
            ('PADDING', (0, 0), (-1, -1), 7),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph('Complaint Description', heading_style))
        story.append(Paragraph(complaint.description, styles['BodyText']))
        if complaint.resolution_summary and mode == 'resolution':
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph('Resolution Notes', heading_style))
            story.append(Paragraph(complaint.resolution_summary, styles['BodyText']))
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph(f'Generated on {datetime.utcnow().strftime("%d %b %Y, %I:%M %p UTC")}', styles['BodyText']))
        doc.build(story)
        buffer.seek(0)
        return buffer.read()
    except Exception:
        content = f"{mode.upper()}\nComplaint ID: {complaint.complaint_id}\nStatus: {complaint.get_status_label()}\n"
        return content.encode('utf-8')
