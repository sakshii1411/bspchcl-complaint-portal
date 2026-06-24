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
    """Generate a stateless HMAC CSRF token — works across multiple gunicorn workers."""
    import hmac, hashlib, time
    # Use session id + day bucket so token rotates daily but works across workers
    session_id = session.get('_uid', '')
    if not session_id:
        session_id = secrets.token_hex(8)
        session['_uid'] = session_id
    day = str(int(time.time()) // 86400)
    secret = current_app.config.get('SECRET_KEY', 'fallback')
    msg = f'{session_id}:{day}'
    token = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return token


def validate_csrf_token():
    """Validate HMAC CSRF token — accepts today and yesterday to handle midnight edge case."""
    import hmac as hmac_mod, hashlib, time
    token = request.form.get('_csrf_token') or request.headers.get('X-CSRFToken')
    if not token:
        abort(400, description='Missing security token.')
    session_id = session.get('_uid', '')
    secret = current_app.config.get('SECRET_KEY', 'fallback')
    now_day = int(time.time()) // 86400
    valid = False
    for day_offset in [0, -1]:  # Accept today and yesterday
        day = str(now_day + day_offset)
        msg = f'{session_id}:{day}'
        expected = hmac_mod.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        if hmac_mod.compare_digest(token, expected):
            valid = True
            break
    if not valid:
        abort(400, description='Invalid security token. Please refresh and try again.')


# ── File Helpers ─────────────────────────────────────────────────────────────

def allowed_file(filename):
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'pdf'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def save_uploaded_file(file, subfolder='complaints'):
    """Upload file to Cloudinary (if configured) or local disk.
    Returns a URL string for Cloudinary, or a relative path for local.
    """
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

    # ── Cloudinary upload ──────────────────────────────────────────────────────
    if current_app.config.get('USE_CLOUDINARY'):
        try:
            import cloudinary
            import cloudinary.uploader
            cloudinary.config(
                cloud_name = current_app.config['CLOUDINARY_CLOUD_NAME'],
                api_key    = current_app.config['CLOUDINARY_API_KEY'],
                api_secret = current_app.config['CLOUDINARY_API_SECRET'],
            )
            file.stream.seek(0)
            result = cloudinary.uploader.upload(
                file.stream,
                folder          = f'bsphcl/{subfolder}',
                resource_type   = 'auto',
                use_filename    = False,
                unique_filename = True,
            )
            # Return full CDN URL — stored directly in DB
            return result['secure_url']
        except Exception as e:
            current_app.logger.error(f'Cloudinary upload failed: {e}')
            # Fall through to local storage as fallback

    # ── Local disk fallback ────────────────────────────────────────────────────
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{''.join(random.choices(string.ascii_lowercase + string.digits, k=20))}.{ext}"
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, unique_name)
    file.stream.seek(0)
    file.save(filepath)
    return os.path.join(subfolder, unique_name)


def get_file_url(path_or_url):
    """Return a usable URL for a stored file path or Cloudinary URL."""
    if not path_or_url:
        return None
    if path_or_url.startswith('http://') or path_or_url.startswith('https://'):
        return path_or_url
    from flask import url_for
    return url_for('static', filename=f'uploads/{path_or_url}')


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
    """Generate a professional government-style PDF for complaint acknowledgement or resolution."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable, KeepTogether)
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

        # ── Colors ──────────────────────────────────────────────────────────────
        MAROON  = colors.HexColor('#8B1A1A')
        NAVY    = colors.HexColor('#1A3A5C')
        NAVY_DK = colors.HexColor('#122840')
        NAVY_LT = colors.HexColor('#eaf0f7')
        GOLD    = colors.HexColor('#C8860A')
        GREY    = colors.HexColor('#666666')
        BORDER  = colors.HexColor('#D8D8D8')
        WHITE   = colors.white
        BLACK   = colors.HexColor('#1a1a1a')

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=1.8*cm, rightMargin=1.8*cm,
            topMargin=1.5*cm, bottomMargin=2*cm,
            title=f"BSPHCL {mode.replace('_',' ').title()} — {complaint.complaint_id}",
            author="Bihar State Power Holding Company Limited",
        )

        styles = getSampleStyleSheet()

        # Custom styles
        def S(name, **kw):
            return ParagraphStyle(name, parent=styles['Normal'], **kw)

        gov_title   = S('GovTitle',   fontSize=8,  textColor=WHITE,  fontName='Helvetica-Bold',
                        alignment=TA_CENTER, spaceAfter=0, leading=12)
        org_name    = S('OrgName',    fontSize=14, textColor=WHITE,  fontName='Helvetica-Bold',
                        alignment=TA_CENTER, spaceAfter=2, leading=17)
        org_sub     = S('OrgSub',     fontSize=8,  textColor=colors.HexColor('#ccddee'),
                        fontName='Helvetica', alignment=TA_CENTER, spaceAfter=0)
        doc_title   = S('DocTitle',   fontSize=13, textColor=MAROON, fontName='Helvetica-Bold',
                        alignment=TA_CENTER, spaceAfter=3, leading=16)
        section_hd  = S('SectionHd', fontSize=9.5,textColor=WHITE,  fontName='Helvetica-Bold',
                        alignment=TA_LEFT,  spaceAfter=0, leading=13)
        body        = S('Body',       fontSize=9.5,textColor=BLACK,  fontName='Helvetica',
                        spaceAfter=4, leading=14)
        label_cell  = S('LabelCell',  fontSize=9,  textColor=NAVY,   fontName='Helvetica-Bold',
                        spaceAfter=0)
        value_cell  = S('ValueCell',  fontSize=9,  textColor=BLACK,  fontName='Helvetica',
                        spaceAfter=0)
        footer_txt  = S('Footer',     fontSize=7.5,textColor=GREY,   fontName='Helvetica',
                        alignment=TA_CENTER)

        story = []
        W = doc.width

        # ── 1. Government header block ──────────────────────────────────────────
        header_data = [[
            Paragraph('GOVERNMENT OF BIHAR', gov_title),
            Paragraph('बिहार स्टेट पॉवर होल्डिंग कंपनी लिमिटेड', org_name),
            Paragraph('Bihar State Power Holding Company Limited', org_sub),
            Paragraph('1st Floor, Vidyut Bhawan, Jawahar Lal Nehru Marg, Patna – 800 001', org_sub),
        ]]
        header_table = Table([[col] for col in header_data[0]], colWidths=[W])
        header_table.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,-1), NAVY_DK),
            ('TOPPADDING',   (0,0), (-1,-1), 6),
            ('BOTTOMPADDING',(0,0), (-1,-1), 6),
            ('LEFTPADDING',  (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(header_table)

        # Maroon separator
        story.append(Table([['']], colWidths=[W],
                           style=TableStyle([('BACKGROUND',(0,0),(-1,-1),MAROON),
                                             ('ROWHEIGHT',(0,0),(-1,-1),4)])))
        story.append(Spacer(1, 0.25*cm))

        # ── 2. Document title ───────────────────────────────────────────────────
        doc_type = 'COMPLAINT ACKNOWLEDGEMENT SLIP' if mode == 'acknowledgement' else 'COMPLAINT RESOLUTION REPORT'
        story.append(Paragraph(doc_type, doc_title))
        story.append(HRFlowable(width=W, thickness=1, color=BORDER, spaceAfter=6))

        # ── 3. Complaint ID + Date banner ───────────────────────────────────────
        banner_data = [[
            Paragraph(f'<b>Complaint ID:</b> {complaint.complaint_id}', S('B1', fontSize=10, textColor=NAVY, fontName='Helvetica-Bold')),
            Paragraph(f'<b>Status:</b> {complaint.get_status_label()}', S('B2', fontSize=10, textColor=MAROON, fontName='Helvetica-Bold', alignment=TA_CENTER)),
            Paragraph(f'<b>Filed:</b> {complaint.created_at.strftime("%d %b %Y")}', S('B3', fontSize=9.5, textColor=GREY, fontName='Helvetica', alignment=TA_RIGHT)),
        ]]
        banner = Table(banner_data, colWidths=[W*0.4, W*0.3, W*0.3])
        banner.setStyle(TableStyle([
            ('BACKGROUND',   (0,0),(-1,-1), NAVY_LT),
            ('ROWBACKGROUNDS',(0,0),(-1,-1), [NAVY_LT]),
            ('BOX',          (0,0),(-1,-1), 0.5, NAVY),
            ('TOPPADDING',   (0,0),(-1,-1), 7),
            ('BOTTOMPADDING',(0,0),(-1,-1), 7),
            ('LEFTPADDING',  (0,0),(-1,-1), 10),
            ('RIGHTPADDING', (0,0),(-1,-1), 10),
            ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
        ]))
        story.append(banner)
        story.append(Spacer(1, 0.3*cm))

        # ── 4. Section header helper ────────────────────────────────────────────
        def section_header(title):
            t = Table([[Paragraph(title.upper(), section_hd)]], colWidths=[W])
            t.setStyle(TableStyle([
                ('BACKGROUND',   (0,0),(-1,-1), NAVY),
                ('TOPPADDING',   (0,0),(-1,-1), 5),
                ('BOTTOMPADDING',(0,0),(-1,-1), 5),
                ('LEFTPADDING',  (0,0),(-1,-1), 10),
            ]))
            return t

        # ── 5. Consumer information ─────────────────────────────────────────────
        story.append(section_header('Consumer Information'))
        consumer_data = [
            [Paragraph('Name', label_cell),          Paragraph(user.name, value_cell),
             Paragraph('Mobile', label_cell),         Paragraph(user.mobile or 'N/A', value_cell)],
            [Paragraph('Consumer Number', label_cell),Paragraph(complaint.consumer_number or user.consumer_number or 'N/A', value_cell),
             Paragraph('Meter Number', label_cell),   Paragraph(complaint.meter_number or 'N/A', value_cell)],
            [Paragraph('District', label_cell),       Paragraph((complaint.district or user.district or 'N/A').title(), value_cell),
             Paragraph('State', label_cell),          Paragraph('Bihar', value_cell)],
        ]
        ct = Table(consumer_data, colWidths=[W*0.18, W*0.32, W*0.18, W*0.32])
        ct.setStyle(TableStyle([
            ('GRID',         (0,0),(-1,-1), 0.3, BORDER),
            ('BACKGROUND',   (0,0),(0,-1), NAVY_LT),
            ('BACKGROUND',   (2,0),(2,-1), NAVY_LT),
            ('TOPPADDING',   (0,0),(-1,-1), 6),
            ('BOTTOMPADDING',(0,0),(-1,-1), 6),
            ('LEFTPADDING',  (0,0),(-1,-1), 8),
            ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
        ]))
        story.append(ct)
        story.append(Spacer(1, 0.25*cm))

        # ── 6. Complaint details ────────────────────────────────────────────────
        story.append(section_header('Complaint Details'))
        details_data = [
            [Paragraph('Subject', label_cell),          Paragraph(complaint.subject, value_cell)],
            [Paragraph('Category', label_cell),         Paragraph(complaint.get_category_label(), value_cell)],
            [Paragraph('Priority', label_cell),         Paragraph(complaint.get_priority_label(), value_cell)],
            [Paragraph('Department', label_cell),       Paragraph(complaint.department or 'Pending assignment', value_cell)],
            [Paragraph('Assigned Officer', label_cell), Paragraph(complaint.assignee.name if complaint.assignee else 'Pending assignment', value_cell)],
            [Paragraph('Expected Resolution', label_cell), Paragraph(
                complaint.expected_resolution_date.strftime('%d %b %Y') if complaint.expected_resolution_date else 'To be updated',
                value_cell)],
        ]
        if mode == 'resolution':
            details_data += [
                [Paragraph('Resolved On', label_cell), Paragraph(
                    complaint.resolved_at.strftime('%d %b %Y, %I:%M %p') if complaint.resolved_at else 'Not yet resolved',
                    value_cell)],
            ]
        dt = Table(details_data, colWidths=[W*0.25, W*0.75])
        dt.setStyle(TableStyle([
            ('GRID',         (0,0),(-1,-1), 0.3, BORDER),
            ('BACKGROUND',   (0,0),(0,-1), NAVY_LT),
            ('TOPPADDING',   (0,0),(-1,-1), 6),
            ('BOTTOMPADDING',(0,0),(-1,-1), 6),
            ('LEFTPADDING',  (0,0),(-1,-1), 8),
            ('VALIGN',       (0,0),(-1,-1), 'TOP'),
            ('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white, colors.HexColor('#f9f9f9')]),
        ]))
        story.append(dt)
        story.append(Spacer(1, 0.25*cm))

        # ── 7. Description ──────────────────────────────────────────────────────
        story.append(section_header('Complaint Description'))
        desc_table = Table([[Paragraph(complaint.description, body)]], colWidths=[W])
        desc_table.setStyle(TableStyle([
            ('BOX',         (0,0),(-1,-1), 0.3, BORDER),
            ('TOPPADDING',  (0,0),(-1,-1), 8),
            ('BOTTOMPADDING',(0,0),(-1,-1), 8),
            ('LEFTPADDING', (0,0),(-1,-1), 10),
        ]))
        story.append(desc_table)
        story.append(Spacer(1, 0.25*cm))

        # ── 8. Resolution summary (if resolution report) ────────────────────────
        if mode == 'resolution' and complaint.resolution_summary:
            story.append(section_header('Resolution Summary'))
            res_table = Table([[Paragraph(complaint.resolution_summary, body)]], colWidths=[W])
            res_table.setStyle(TableStyle([
                ('BOX',          (0,0),(-1,-1), 0.3, BORDER),
                ('BACKGROUND',   (0,0),(-1,-1), colors.HexColor('#e6f4ea')),
                ('TOPPADDING',   (0,0),(-1,-1), 8),
                ('BOTTOMPADDING',(0,0),(-1,-1), 8),
                ('LEFTPADDING',  (0,0),(-1,-1), 10),
            ]))
            story.append(res_table)
            story.append(Spacer(1, 0.25*cm))

        # ── 9. Important note ───────────────────────────────────────────────────
        note_text = (
            '<b>Important:</b> Please quote your Complaint ID <b>{}</b> in all future correspondence '
            'with BSPHCL regarding this complaint. For escalation, contact the Consumer Grievance '
            'Cell at <b>1912</b> (Toll-free, 24x7) or email <b>consumercomplaint.bsphcl@gmail.com</b>.'
            if mode == 'acknowledgement' else
            '<b>Note:</b> If you are not satisfied with the resolution provided, you may reopen this '
            'complaint within 7 days by logging into the Consumer Portal. For further escalation, '
            'contact the Consumer Grievance Cell at <b>1912</b> or email <b>consumercomplaint.bsphcl@gmail.com</b>.'
        ).format(complaint.complaint_id)

        note_table = Table([[Paragraph(note_text, S('Note', fontSize=8.5, textColor=colors.HexColor('#5a3a00'), fontName='Helvetica'))]], colWidths=[W])
        note_table.setStyle(TableStyle([
            ('BACKGROUND',   (0,0),(-1,-1), colors.HexColor('#fff8e1')),
            ('BOX',          (0,0),(-1,-1), 0.5, GOLD),
            ('LEFTBORDER',   (0,0),(0,-1),  3,   GOLD),
            ('TOPPADDING',   (0,0),(-1,-1), 7),
            ('BOTTOMPADDING',(0,0),(-1,-1), 7),
            ('LEFTPADDING',  (0,0),(-1,-1), 10),
        ]))
        story.append(note_table)
        story.append(Spacer(1, 0.35*cm))

        # ── 10. Footer ──────────────────────────────────────────────────────────
        story.append(HRFlowable(width=W, thickness=0.5, color=BORDER))
        story.append(Spacer(1, 0.15*cm))
        gen_time = datetime.utcnow().strftime("%d %b %Y, %I:%M %p UTC")
        story.append(Paragraph(
            f'Generated on {gen_time} &nbsp;|&nbsp; Bihar State Power Holding Company Limited ' +
            f'&nbsp;|&nbsp; CIN: U40102BR2012SGC018495',
            footer_txt
        ))
        story.append(Paragraph(
            'This is a system-generated document and does not require a physical signature.',
            footer_txt
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer.read()

    except Exception as e:
        import traceback
        current_app.logger.error(f'PDF generation error: {traceback.format_exc()}')
        # Plain text fallback
        lines = [
            f"BSPHCL Consumer Complaint Portal",
            f"{'='*50}",
            f"Complaint ID : {complaint.complaint_id}",
            f"Consumer     : {user.name}",
            f"Status       : {complaint.get_status_label()}",
            f"Category     : {complaint.get_category_label()}",
            f"Priority     : {complaint.get_priority_label()}",
            f"Filed On     : {complaint.created_at.strftime('%d %b %Y')}",
            f"",
            f"Description:",
            complaint.description,
        ]
        if mode == 'resolution' and complaint.resolution_summary:
            lines += ["", "Resolution:", complaint.resolution_summary]
        return "\n".join(lines).encode('utf-8')
