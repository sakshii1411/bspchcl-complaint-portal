from datetime import datetime, timedelta
import io

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, send_file, abort, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func, or_

from extensions import db
from models import User, Complaint, Reply, OTP, Notification, ComplaintAttachment, ComplaintLog, SatisfactionRating
from utils import (
    generate_complaint_id, generate_consumer_number, create_otp, verify_otp,
    send_otp_email, send_complaint_confirmation, send_status_email,
    save_uploaded_file, generate_complaint_pdf, create_notification,
    log_complaint_action
)

main = Blueprint('main', __name__)


def _get_complaint_or_404(complaint_id):
    complaint = Complaint.query.filter_by(complaint_id=complaint_id).first_or_404()
    if complaint.user_id != current_user.id and not current_user.is_staff:
        abort(403)
    return complaint


@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('admin.admin_dashboard' if current_user.is_staff else 'main.dashboard'))
    return redirect(url_for('main.login'))


@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        mobile = request.form.get('mobile', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        district = request.form.get('district', '').strip()
        address = request.form.get('address', '').strip()

        errors = []
        if not all([name, email, mobile, password, confirm]):
            errors.append('All required fields must be filled.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if not mobile.isdigit() or len(mobile) != 10:
            errors.append('Enter a valid 10-digit mobile number.')
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered.')
        if User.query.filter_by(mobile=mobile).first():
            errors.append('Mobile number already registered.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('register.html', form_data=request.form)

        user = User(name=name, email=email, mobile=mobile, district=district, address=address, consumer_number=generate_consumer_number(), role='consumer')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        create_notification(user.id, 'Account created', 'Your consumer account has been created successfully.', 'success')
        flash('Registration successful. Please sign in.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', form_data={})


@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')
        if not user.is_active:
            flash('Your account is inactive. Contact support.', 'danger')
            return render_template('login.html')
        if user.is_staff:
            flash('Please use the staff login page.', 'warning')
            return redirect(url_for('admin.admin_login'))
        user.last_login = datetime.utcnow()
        db.session.commit()
        login_user(user, remember=bool(request.form.get('remember')))
        flash(f'Welcome back, {user.name.split()[0]}.', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('login.html')


@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.login'))


@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_staff:
        return redirect(url_for('admin.admin_dashboard'))
    complaints = Complaint.query.filter_by(user_id=current_user.id).all()
    total = len(complaints)
    pending = sum(1 for c in complaints if c.status == 'pending')
    reviewing = sum(1 for c in complaints if c.status in ('under_review', 'assigned', 'in_progress', 'reopened', 'escalated'))
    resolved = sum(1 for c in complaints if c.status == 'resolved')
    closed = sum(1 for c in complaints if c.status == 'closed')
    recent = Complaint.query.filter_by(user_id=current_user.id).order_by(Complaint.created_at.desc()).limit(5).all()
    notifs = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()
    cat_data = {}
    for c in complaints:
        cat_data[c.get_category_label()] = cat_data.get(c.get_category_label(), 0) + 1
    return render_template('dashboard.html', total=total, pending=pending, reviewing=reviewing, resolved=resolved, closed=closed, recent=recent, notifs=notifs, cat_data=cat_data)


@main.route('/track', methods=['GET', 'POST'])
def track_complaint():
    complaint = None
    not_found = False
    if request.method == 'POST':
        complaint_id = request.form.get('complaint_id', '').strip().upper()
        consumer_number = request.form.get('consumer_number', '').strip().upper()
        if complaint_id and consumer_number:
            complaint = Complaint.query.filter_by(
                complaint_id=complaint_id,
                consumer_number=consumer_number
            ).first()
            if not complaint:
                not_found = True
        else:
            not_found = True
    return render_template('help_desk.html', tracked_complaint=complaint, not_found=not_found)


@main.route('/complaint/new', methods=['GET', 'POST'])
@login_required
def new_complaint():
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '')
        sub_cat = request.form.get('sub_category', '').strip()
        priority = request.form.get('priority', 'medium')
        district = request.form.get('district', current_user.district or '').strip()
        address = request.form.get('address', '').strip()
        meter_no = request.form.get('meter_number', '').strip()
        cons_no = request.form.get('consumer_number', current_user.consumer_number or '').strip()

        if not all([subject, description, category, cons_no]):
            flash('Subject, description, category and consumer number are required.', 'danger')
            return render_template('complaint_form.html', categories=Complaint.CATEGORIES, priorities=Complaint.PRIORITIES, form_data=request.form)
        if len(description) < 20:
            flash('Description must be at least 20 characters.', 'danger')
            return render_template('complaint_form.html', categories=Complaint.CATEGORIES, priorities=Complaint.PRIORITIES, form_data=request.form)

        auto_priority_map = {'transformer': 'high', 'power_outage': 'high', 'meter_fault': 'medium', 'billing': 'medium', 'low_voltage': 'high', 'safety': 'urgent'}
        priority = auto_priority_map.get(category, priority)

        cid = generate_complaint_id()
        while Complaint.query.filter_by(complaint_id=cid).first():
            cid = generate_complaint_id()

        complaint = Complaint(
            complaint_id=cid, user_id=current_user.id, subject=subject, description=description,
            category=category, sub_category=sub_cat, priority=priority, district=district,
            address=address, meter_number=meter_no, consumer_number=cons_no,
            expected_resolution_date=datetime.utcnow() + timedelta(days={'urgent': 1, 'high': 2, 'medium': 4, 'low': 7}.get(priority, 4))
        )
        db.session.add(complaint)
        db.session.commit()

        files = request.files.getlist('attachments') or []
        first_path = None
        for f in files:
            path = save_uploaded_file(f, 'complaints')
            if path:
                db.session.add(ComplaintAttachment(complaint_id=complaint.id, file_path=path, original_name=f.filename))
                first_path = first_path or path
        complaint.attachment = first_path
        db.session.commit()

        create_notification(current_user.id, f'Complaint registered: {cid}', 'Your complaint has been filed and is awaiting review.', 'success', cid)
        log_complaint_action(complaint, 'created', 'Complaint registered by consumer.', current_user.id, True)
        send_complaint_confirmation(current_user.email, cid, subject, current_user.name)
        flash(f'Complaint {cid} filed successfully.', 'success')
        return redirect(url_for('main.complaint_detail', complaint_id=cid))

    return render_template('complaint_form.html', categories=Complaint.CATEGORIES, priorities=Complaint.PRIORITIES, form_data={})


@main.route('/complaint/<complaint_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_complaint(complaint_id):
    complaint = _get_complaint_or_404(complaint_id)
    if not complaint.can_be_edited_by_user:
        flash('This complaint can no longer be edited because review has already started.', 'warning')
        return redirect(url_for('main.complaint_detail', complaint_id=complaint.complaint_id))

    if request.method == 'POST':
        complaint.subject = request.form.get('subject', complaint.subject).strip()
        complaint.description = request.form.get('description', complaint.description).strip()
        complaint.sub_category = request.form.get('sub_category', complaint.sub_category or '').strip()
        complaint.priority = request.form.get('priority', complaint.priority)
        complaint.district = request.form.get('district', complaint.district or '').strip()
        complaint.address = request.form.get('address', complaint.address or '').strip()
        complaint.meter_number = request.form.get('meter_number', complaint.meter_number or '').strip()
        db.session.commit()
        log_complaint_action(complaint, 'edited', 'Complaint details updated by consumer before review.', current_user.id, True)
        flash('Complaint updated successfully.', 'success')
        return redirect(url_for('main.complaint_detail', complaint_id=complaint.complaint_id))

    return render_template('complaint_form.html', categories=Complaint.CATEGORIES, priorities=Complaint.PRIORITIES, form_data=complaint, edit_mode=True, complaint=complaint)


@main.route('/complaints')
@login_required
def complaint_history():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    category = request.args.get('category', 'all')
    search = request.args.get('search', '').strip()
    query = Complaint.query.filter_by(user_id=current_user.id)
    if status != 'all':
        query = query.filter_by(status=status)
    if category != 'all':
        query = query.filter_by(category=category)
    if search:
        query = query.filter(or_(Complaint.complaint_id.ilike(f'%{search}%'), Complaint.subject.ilike(f'%{search}%'), Complaint.consumer_number.ilike(f'%{search}%')))
    pagination = query.order_by(Complaint.created_at.desc()).paginate(page=page, per_page=8)
    all_complaints = Complaint.query.filter_by(user_id=current_user.id).all()
    total = len(all_complaints)
    resolved = sum(1 for c in all_complaints if c.status == 'resolved')
    pending = sum(1 for c in all_complaints if c.status == 'pending')
    rejected = sum(1 for c in all_complaints if c.status == 'rejected')
    return render_template('complaint_history.html', pagination=pagination, categories=Complaint.CATEGORIES, statuses=Complaint.STATUSES, current_status=status, current_category=category, search=search, total=total, resolved=resolved, pending=pending, rejected=rejected)


@main.route('/complaint/<complaint_id>', methods=['GET', 'POST'])
@login_required
def complaint_detail(complaint_id):
    complaint = _get_complaint_or_404(complaint_id)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'reply':
            msg = request.form.get('message', '').strip()
            if msg:
                db.session.add(Reply(complaint_id=complaint.id, user_id=current_user.id, message=msg, is_admin_reply=False))
                db.session.commit()
                log_complaint_action(complaint, 'consumer_reply', 'Consumer added a follow-up message.', current_user.id, True)
                flash('Reply submitted.', 'success')
        elif action == 'close' and complaint.status == 'resolved':
            complaint.is_closed_by_user = True
            complaint.status = 'closed'
            complaint.updated_at = datetime.utcnow()
            db.session.commit()
            create_notification(current_user.id, f'Complaint closed: {complaint_id}', 'The complaint has been marked as closed.', 'success', complaint_id)
            log_complaint_action(complaint, 'closed', 'Complaint closed by consumer after resolution.', current_user.id, True)
            flash('Complaint closed.', 'success')
        elif action == 'reopen' and complaint.status in {'resolved', 'closed'}:
            reason = request.form.get('reopen_reason', '').strip()
            if len(reason) < 10:
                flash('Please provide a brief reason for reopening the complaint.', 'danger')
            else:
                complaint.status = 'reopened'
                complaint.reopen_count += 1
                complaint.is_closed_by_user = False
                complaint.updated_at = datetime.utcnow()
                db.session.commit()
                create_notification(current_user.id, f'Complaint reopened: {complaint_id}', 'Your complaint has been reopened and routed for review.', 'warning', complaint_id)
                log_complaint_action(complaint, 'reopened', f'Complaint reopened by consumer. Reason: {reason}', current_user.id, True)
                flash('Complaint reopened successfully.', 'success')
        elif action == 'rate' and complaint.status in {'resolved', 'closed'}:
            rating_value = request.form.get('rating', type=int)
            feedback = request.form.get('feedback', '').strip()
            if rating_value and 1 <= rating_value <= 5 and not complaint.rating:
                db.session.add(SatisfactionRating(complaint_id=complaint.id, user_id=current_user.id, rating=rating_value, feedback=feedback))
                db.session.commit()
                flash('Thank you for your feedback.', 'success')
        return redirect(url_for('main.complaint_detail', complaint_id=complaint.complaint_id))

    replies = Reply.query.filter_by(complaint_id=complaint.id).order_by(Reply.created_at.asc()).all()
    attachments = ComplaintAttachment.query.filter_by(complaint_id=complaint.id).order_by(ComplaintAttachment.uploaded_at.asc()).all()
    timeline = ComplaintLog.query.filter_by(complaint_id=complaint.id).filter_by(visible_to_user=True).order_by(ComplaintLog.created_at.asc()).all()
    return render_template('complaint_detail.html', complaint=complaint, replies=replies, attachments=attachments, timeline=timeline)


@main.route('/complaint/<complaint_id>/receipt')
@login_required
def download_receipt(complaint_id):
    complaint = _get_complaint_or_404(complaint_id)
    pdf_bytes = generate_complaint_pdf(complaint, complaint.user, mode='acknowledgement')
    return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=f'Acknowledgement_{complaint_id}.pdf')


@main.route('/complaint/<complaint_id>/resolution-report')
@login_required
def download_resolution_report(complaint_id):
    complaint = _get_complaint_or_404(complaint_id)
    pdf_bytes = generate_complaint_pdf(complaint, complaint.user, mode='resolution')
    return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=f'Resolution_Report_{complaint_id}.pdf')


@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_profile':
            name = request.form.get('name', '').strip()
            mobile = request.form.get('mobile', '').strip()
            district = request.form.get('district', '').strip()
            address = request.form.get('address', '').strip()
            if not name or not mobile:
                flash('Name and mobile are required.', 'danger')
                return redirect(url_for('main.profile'))
            existing = User.query.filter_by(mobile=mobile).first()
            if existing and existing.id != current_user.id:
                flash('Mobile number is already in use.', 'danger')
                return redirect(url_for('main.profile'))
            pic = request.files.get('profile_pic')
            if pic and pic.filename:
                pic_path = save_uploaded_file(pic, 'profiles')
                if pic_path:
                    current_user.profile_pic = pic_path
            current_user.name = name
            current_user.mobile = mobile
            current_user.district = district
            current_user.address = address
            db.session.commit()
            flash('Profile updated successfully.', 'success')
        elif action == 'change_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')
            if not current_user.check_password(current_pw):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('main.profile'))
            if new_pw != confirm_pw:
                flash('New passwords do not match.', 'danger')
                return redirect(url_for('main.profile'))
            if len(new_pw) < 8:
                flash('Password must be at least 8 characters.', 'danger')
                return redirect(url_for('main.profile'))
            current_user.set_password(new_pw)
            db.session.commit()
            flash('Password changed successfully.', 'success')
        return redirect(url_for('main.profile'))

    total_complaints = Complaint.query.filter_by(user_id=current_user.id).count()
    resolved = Complaint.query.filter_by(user_id=current_user.id, status='resolved').count()
    filled_fields = sum(bool(v) for v in [current_user.name, current_user.email, current_user.mobile, current_user.district, current_user.address, current_user.consumer_number, current_user.profile_pic])
    profile_completion = int((filled_fields / 7) * 100)
    return render_template('profile.html', total_complaints=total_complaints, resolved=resolved, profile_completion=profile_completion)


@main.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('notifications.html', notifs=notifs)


@main.route('/notifications/<int:notif_id>/toggle', methods=['POST'])
@login_required
def toggle_notification(notif_id):
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    notif.is_read = not notif.is_read
    db.session.commit()
    return redirect(url_for('main.notifications'))


@main.route('/help')
def help_desk():
    return render_template('help_desk.html', tracked_complaint=None)


@main.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('No account found with that email.', 'danger')
            return render_template('forgot_password.html')
        otp_code = create_otp(email)
        sent = send_otp_email(email, otp_code, user.name)
        if not sent:
            flash('Unable to send OTP email at the moment. Please try again later.', 'danger')
            return render_template('forgot_password.html')
        session['reset_email'] = email
        flash('An OTP has been sent to your registered email address.', 'success')
        return redirect(url_for('main.reset_password'))
    return render_template('forgot_password.html')


@main.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    email = session.get('reset_email')
    if not email:
        flash('Please begin the password reset process again.', 'warning')
        return redirect(url_for('main.forgot_password'))
    if request.method == 'POST':
        otp_code = request.form.get('otp', '').strip()
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')
        if not verify_otp(email, otp_code):
            flash('Invalid or expired OTP.', 'danger')
            return render_template('reset_password.html')
        if new_pw != confirm_pw:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html')
        if len(new_pw) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('reset_password.html')
        user = User.query.filter_by(email=email).first()
        user.set_password(new_pw)
        db.session.commit()
        session.pop('reset_email', None)
        flash('Password reset successful. Please sign in.', 'success')
        return redirect(url_for('main.login'))
    return render_template('reset_password.html')


@main.route('/api/notif-count')
@login_required
def notif_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})
