from datetime import datetime, timedelta
import io

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort, send_file
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func, or_
from openpyxl import Workbook

from extensions import db
from models import User, Complaint, Reply, Notification, ComplaintLog, ComplaintAttachment
from utils import (
    admin_required, create_notification, log_complaint_action, audit_admin_action,
    complaints_to_csv_bytes, generate_complaint_pdf, send_status_email
)

admin = Blueprint('admin', __name__)


def _require_role(*allowed_roles):
    if current_user.role not in allowed_roles and current_user.role != 'super_admin':
        abort(403)


def _staff_query():
    return User.query.filter(User.role.in_(['super_admin', 'operator', 'complaint_officer', 'field_staff']))


@admin.route('/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and current_user.is_staff:
        return redirect(url_for('admin.admin_dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password) or not user.is_staff:
            flash('Invalid staff credentials.', 'danger')
            return render_template('admin/login_admin.html')
        user.last_login = datetime.utcnow()
        db.session.commit()
        login_user(user)
        flash('Signed in successfully.', 'success')
        return redirect(url_for('admin.admin_dashboard'))
    return render_template('admin/login_admin.html')


@admin.route('/logout')
@login_required
@admin_required
def admin_logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('admin.admin_login'))


@admin.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    total_c = Complaint.query.count()
    pending_c = Complaint.query.filter_by(status='pending').count()
    review_c = Complaint.query.filter(Complaint.status.in_(['under_review', 'assigned', 'in_progress', 'reopened'])).count()
    resolved_c = Complaint.query.filter_by(status='resolved').count()
    closed_c = Complaint.query.filter_by(status='closed').count()
    rejected_c = Complaint.query.filter_by(status='rejected').count()
    overdue_c = sum(1 for c in Complaint.query.all() if c.is_overdue)
    total_users = User.query.filter_by(is_admin=False).count()
    active_users = User.query.filter_by(is_admin=False, is_active=True).count()
    inactive_users = User.query.filter_by(is_admin=False, is_active=False).count()

    resolved_list = Complaint.query.filter(Complaint.resolved_at.isnot(None)).all()
    avg_resolution_days = '-'
    if resolved_list:
        avg_resolution_days = round(
            sum(max((c.resolved_at - c.created_at).days, 1) for c in resolved_list) / len(resolved_list),
            1
        )
    resolution_rate = round(((resolved_c + closed_c) / total_c * 100), 1) if total_c else 0

    today = datetime.utcnow().date()
    trend_labels, trend_data = [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = Complaint.query.filter(func.date(Complaint.created_at) == day).count()
        trend_labels.append(day.strftime('%a'))
        trend_data.append(count)

    cat_rows = db.session.query(Complaint.category, func.count(Complaint.id)).group_by(Complaint.category).all()
    cat_labels = [r[0].replace('_', ' ').title() for r in cat_rows]
    cat_values = [r[1] for r in cat_rows]

    pri_rows = db.session.query(Complaint.priority, func.count(Complaint.id)).group_by(Complaint.priority).all()
    pri_labels = [r[0].title() for r in pri_rows]
    pri_values = [r[1] for r in pri_rows]

    district_counter = {}
    for c in Complaint.query.all():
        district_name = c.district.title() if c.district else 'Not specified'
        district_counter[district_name] = district_counter.get(district_name, 0) + 1
    district_labels = list(district_counter.keys())[:8]
    district_values = list(district_counter.values())[:8]

    recent_activity = ComplaintLog.query.order_by(ComplaintLog.created_at.desc()).limit(12).all()
    return render_template('admin/dashboard_admin.html', total_c=total_c, pending_c=pending_c, review_c=review_c, resolved_c=resolved_c, closed_c=closed_c, rejected_c=rejected_c, overdue_c=overdue_c, total_users=total_users, active_users=active_users, inactive_users=inactive_users, resolution_rate=resolution_rate, avg_resolution_days=avg_resolution_days, trend_labels=trend_labels, trend_data=trend_data, cat_labels=cat_labels, cat_values=cat_values, pri_labels=pri_labels, pri_values=pri_values, district_labels=district_labels, district_values=district_values, recent_activity=recent_activity)


@admin.route('/users')
@login_required
@admin_required
def manage_users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status = request.args.get('status', 'all')
    query = User.query.filter_by(is_admin=False).filter(User.role == 'consumer')
    if search:
        query = query.filter(or_(User.name.ilike(f'%{search}%'), User.email.ilike(f'%{search}%'), User.mobile.ilike(f'%{search}%'), User.consumer_number.ilike(f'%{search}%')))
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=10)
    return render_template('admin/manage_users.html', pagination=pagination, search=search, status=status)


@admin.route('/users/<int:user_id>')
@login_required
@admin_required
def user_details(user_id):
    user = User.query.get_or_404(user_id)
    complaints = Complaint.query.filter_by(user_id=user_id).order_by(Complaint.created_at.desc()).limit(10).all()
    total = Complaint.query.filter_by(user_id=user_id).count()
    resolved = Complaint.query.filter(Complaint.user_id == user_id, Complaint.status.in_(['resolved', 'closed'])).count()
    return render_template('admin/user_details.html', user=user, complaints=complaints, total=total, resolved=resolved)


@admin.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.name = request.form.get('name', user.name).strip()
        user.mobile = request.form.get('mobile', user.mobile).strip()
        user.district = request.form.get('district', user.district or '').strip()
        user.address = request.form.get('address', user.address or '').strip()
        db.session.commit()
        audit_admin_action('edit_user', f'Updated user {user.email}', current_user.id)
        flash('User updated successfully.', 'success')
        return redirect(url_for('admin.user_details', user_id=user_id))
    return render_template('admin/edit_user.html', user=user)


@admin.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    audit_admin_action('toggle_user', f'Changed active state for {user.email} to {user.is_active}', current_user.id)
    flash(f'User {user.name} updated.', 'success')
    return redirect(url_for('admin.manage_users'))


@admin.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    try:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'danger')

    return redirect(url_for('admin.manage_users'))


@admin.route('/complaints')
@login_required
@admin_required
def all_complaints():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    priority = request.args.get('priority', 'all')
    category = request.args.get('category', 'all')
    district = request.args.get('district', 'all')
    search = request.args.get('search', '').strip()

    query = Complaint.query
    if status != 'all':
        query = query.filter_by(status=status)
    if priority != 'all':
        query = query.filter_by(priority=priority)
    if category != 'all':
        query = query.filter_by(category=category)
    if district != 'all':
        query = query.filter_by(district=district)
    if search:
        query = query.filter(or_(Complaint.complaint_id.ilike(f'%{search}%'), Complaint.subject.ilike(f'%{search}%'), Complaint.consumer_number.ilike(f'%{search}%')))

    pagination = query.order_by(Complaint.created_at.desc()).paginate(page=page, per_page=10)
    districts = [d[0] for d in db.session.query(Complaint.district).distinct().all() if d[0]]
    staff_members = _staff_query().all()
    return render_template('admin/all_complaints.html', pagination=pagination, statuses=Complaint.STATUSES, priorities=Complaint.PRIORITIES, categories=Complaint.CATEGORIES, current_status=status, current_priority=priority, current_category=category, current_district=district, districts=districts, search=search, staff_members=staff_members, now=datetime.utcnow())


@admin.route('/complaints/bulk-update', methods=['POST'])
@login_required
@admin_required
def bulk_update_complaints():
    complaint_ids = request.form.getlist('complaint_ids')
    new_status = request.form.get('bulk_status')
    assigned_to = request.form.get('bulk_assigned_to', type=int)
    if not complaint_ids:
        flash('Select at least one complaint for bulk action.', 'warning')
        return redirect(url_for('admin.all_complaints'))
    complaints = Complaint.query.filter(Complaint.id.in_(complaint_ids)).all()
    for complaint in complaints:
        if new_status:
            complaint.status = new_status
            complaint.first_review_at = complaint.first_review_at or datetime.utcnow()
            if new_status == 'resolved':
                complaint.resolved_at = datetime.utcnow()
        if assigned_to:
            complaint.assigned_to = assigned_to
        complaint.updated_at = datetime.utcnow()
    db.session.commit()
    for complaint in complaints:
        log_complaint_action(complaint, 'bulk_update', f'Complaint updated in bulk to {complaint.get_status_label()}.', current_user.id, True)
    audit_admin_action('bulk_update_complaints', f'Bulk updated {len(complaints)} complaints', current_user.id)
    flash('Bulk action applied successfully.', 'success')
    return redirect(url_for('admin.all_complaints'))


@admin.route('/complaints/export/excel')
@login_required
@admin_required
def export_complaints_excel():
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    wb = Workbook()
    ws = wb.active
    ws.title = 'Complaints'
    ws.append(['Complaint ID', 'Consumer No.', 'Subject', 'Category', 'Priority', 'Status', 'District', 'Department', 'Assigned To', 'Expected Resolution', 'Created At'])
    for c in complaints:
        ws.append([c.complaint_id, c.consumer_number, c.subject, c.get_category_label(), c.get_priority_label(), c.get_status_label(), c.district or '', c.department or '', c.assignee.name if c.assignee else '', c.expected_resolution_date.strftime('%Y-%m-%d') if c.expected_resolution_date else '', c.created_at.strftime('%Y-%m-%d %H:%M')])
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='complaints_export.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@admin.route('/complaints/export/pdf')
@login_required
@admin_required
def export_complaints_pdf():
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        rows = [['Complaint ID', 'Category', 'Status', 'District', 'Priority']]
        for c in complaints[:60]:
            rows.append([c.complaint_id, c.get_category_label(), c.get_status_label(), c.district or '', c.get_priority_label()])
        table = Table(rows, repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1d4ed8')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.25,colors.grey),('FONTSIZE',(0,0),(-1,-1),8)]))
        story=[Paragraph('Complaint Export Summary', styles['Title']), Spacer(1,12), table]
        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name='complaints_export.pdf', mimetype='application/pdf')
    except Exception:
        csv_bytes = complaints_to_csv_bytes(complaints)
        return send_file(io.BytesIO(csv_bytes), as_attachment=True, download_name='complaints_export.csv', mimetype='text/csv')


@admin.route('/complaints/<complaint_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def complaint_detail_admin(complaint_id):
    complaint = Complaint.query.filter_by(complaint_id=complaint_id).first_or_404()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_status':
            new_status = request.form.get('status')
            new_priority = request.form.get('priority')
            admin_note = request.form.get('admin_note', '').strip()
            internal_remarks = request.form.get('internal_remarks', '').strip()
            department = request.form.get('department', '').strip()
            field_unit = request.form.get('field_unit', '').strip()
            assigned_to = request.form.get('assigned_to', type=int)
            expected_date_str = request.form.get('expected_resolution_date', '').strip()
            resolution_summary = request.form.get('resolution_summary', '').strip()

            old_status = complaint.status
            if new_status:
                complaint.status = new_status
                complaint.first_review_at = complaint.first_review_at or datetime.utcnow()
                if new_status == 'resolved':
                    complaint.resolved_at = datetime.utcnow()
                if new_status == 'escalated':
                    complaint.escalated_at = datetime.utcnow()
            if new_priority:
                complaint.priority = new_priority
            if admin_note:
                complaint.admin_note = admin_note
            if internal_remarks:
                complaint.internal_remarks = internal_remarks
            if department:
                complaint.department = department
            if field_unit:
                complaint.field_unit = field_unit
            if assigned_to:
                complaint.assigned_to = assigned_to
            if expected_date_str:
                complaint.expected_resolution_date = datetime.strptime(expected_date_str, '%Y-%m-%d')
            elif not complaint.expected_resolution_date:
                complaint.expected_resolution_date = complaint.default_eta()
            if resolution_summary:
                complaint.resolution_summary = resolution_summary
            complaint.updated_at = datetime.utcnow()
            db.session.commit()

            log_message = f'Status updated from {old_status.replace("_", " ").title()} to {complaint.get_status_label()}.'
            if complaint.assignee:
                log_message += f' Assigned to {complaint.assignee.name}.'
            if complaint.expected_resolution_date:
                log_message += f' Expected resolution by {complaint.expected_resolution_date.strftime("%d %b %Y")}. '
            log_complaint_action(complaint, 'status_update', log_message, current_user.id, True)
            if internal_remarks:
                log_complaint_action(complaint, 'internal_remark', internal_remarks, current_user.id, False)
            create_notification(complaint.user_id, f'Complaint update: {complaint.complaint_id}', f'Your complaint is now {complaint.get_status_label()}.', 'info', complaint.complaint_id)
            send_status_email(complaint.user.email, complaint, complaint.user.name)
            audit_admin_action('update_complaint', f'Updated complaint {complaint.complaint_id}', current_user.id)
            flash('Complaint updated successfully.', 'success')

        elif action == 'reply':
            msg = request.form.get('message', '').strip()
            if msg:
                db.session.add(Reply(complaint_id=complaint.id, user_id=current_user.id, message=msg, is_admin_reply=True))
                db.session.commit()
                log_complaint_action(complaint, 'staff_reply', 'A staff reply was added to the complaint thread.', current_user.id, True)
                create_notification(complaint.user_id, f'New response: {complaint.complaint_id}', 'A new response has been posted by the complaint desk.', 'info', complaint.complaint_id)
                flash('Reply sent.', 'success')

        return redirect(url_for('admin.complaint_detail_admin', complaint_id=complaint_id))

    replies = Reply.query.filter_by(complaint_id=complaint.id).order_by(Reply.created_at.asc()).all()
    attachments = ComplaintAttachment.query.filter_by(complaint_id=complaint.id).order_by(ComplaintAttachment.uploaded_at.asc()).all()
    timeline = ComplaintLog.query.filter_by(complaint_id=complaint.id).order_by(ComplaintLog.created_at.asc()).all()
    user = User.query.get(complaint.user_id)
    staff_members = _staff_query().all()
    return render_template('admin/complaint_detail_admin.html', complaint=complaint, replies=replies, user=user, statuses=Complaint.STATUSES, priorities=Complaint.PRIORITIES, staff_members=staff_members, attachments=attachments, timeline=timeline)




@admin.route('/staff')
@login_required
@admin_required
def manage_staff():
    if current_user.role != 'super_admin':
        flash('Only the administrator can manage staff accounts.', 'warning')
        return redirect(url_for('admin.admin_dashboard'))
    staff_users = User.query.filter(User.role != 'consumer').order_by(User.created_at.desc()).all()
    return render_template('admin/manage_staff.html', users=staff_users)


@admin.route('/staff/add', methods=['POST'])
@login_required
@admin_required
def add_staff():
    if current_user.role != 'super_admin':
        flash('Only the administrator can add staff accounts.', 'warning')
        return redirect(url_for('admin.admin_dashboard'))
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    mobile = request.form.get('mobile', '').strip()
    role = request.form.get('role', '').strip()
    password = request.form.get('password', '').strip()

    if not all([name, email, mobile, role, password]):
        flash('All staff fields are required.', 'danger')
        return redirect(url_for('admin.manage_staff'))

    if User.query.filter_by(email=email).first():
        flash('Email already exists.', 'danger')
        return redirect(url_for('admin.manage_staff'))

    if User.query.filter_by(mobile=mobile).first():
        flash('Mobile number already exists.', 'danger')
        return redirect(url_for('admin.manage_staff'))

    if role not in {'super_admin', 'complaint_officer', 'operator', 'field_staff'}:
        flash('Invalid role selected.', 'danger')
        return redirect(url_for('admin.manage_staff'))

    if len(password) < 8:
        flash('Password must be at least 8 characters.', 'danger')
        return redirect(url_for('admin.manage_staff'))

    user = User(
        name=name,
        email=email,
        mobile=mobile,
        role=role,
        is_admin=True,
        is_active=True,
        department='Complaint Management'
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()
    audit_admin_action('add_staff', f'Added staff user {email} with role {role}', current_user.id)
    flash('Staff member added successfully.', 'success')
    return redirect(url_for('admin.manage_staff'))


@admin.route('/staff/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_staff(user_id):
    if current_user.role != 'super_admin':
        flash('Only the administrator can update staff accounts.', 'warning')
        return redirect(url_for('admin.admin_dashboard'))
    user = User.query.get_or_404(user_id)
    if user.role == 'consumer':
        flash('This action is only for staff accounts.', 'warning')
        return redirect(url_for('admin.manage_staff'))

    user.is_active = not user.is_active
    db.session.commit()
    audit_admin_action('toggle_staff', f'Changed active state for {user.email} to {user.is_active}', current_user.id)
    flash('Staff account updated successfully.', 'success')
    return redirect(url_for('admin.manage_staff'))


@admin.route('/staff/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_staff_password(user_id):
    if current_user.role != 'super_admin':
        flash('Only the administrator can reset staff passwords.', 'warning')
        return redirect(url_for('admin.admin_dashboard'))

    user = User.query.get_or_404(user_id)
    if user.role == 'consumer':
        flash('This action is only for staff accounts.', 'warning')
        return redirect(url_for('admin.manage_staff'))

    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 8:
        flash('Password must be at least 8 characters.', 'danger')
        return redirect(url_for('admin.manage_staff'))

    user.set_password(new_password)
    db.session.commit()
    audit_admin_action('reset_staff_password', f'Reset password for {user.email}', current_user.id)
    flash('Staff password updated successfully.', 'success')
    return redirect(url_for('admin.manage_staff'))


@admin.route('/reports')
@login_required
@admin_required
def reports():
    from_str = request.args.get('from', '').strip()
    to_str = request.args.get('to', '').strip()

    base_query = Complaint.query
    start_dt = None
    end_dt = None

    if from_str:
        try:
            start_dt = datetime.strptime(from_str, '%Y-%m-%d')
            base_query = base_query.filter(Complaint.created_at >= start_dt)
        except ValueError:
            flash('Invalid From date.', 'warning')

    if to_str:
        try:
            end_dt = datetime.strptime(to_str, '%Y-%m-%d') + timedelta(days=1)
            base_query = base_query.filter(Complaint.created_at < end_dt)
        except ValueError:
            flash('Invalid To date.', 'warning')

    complaints = base_query.all()

    total_c = len(complaints)
    resolved_c = sum(1 for c in complaints if c.status in ['resolved', 'closed'])
    pending_c = sum(1 for c in complaints if c.status not in ['resolved', 'closed', 'rejected'])

    resolved_list = [c for c in complaints if c.resolved_at]
    avg_resolution_days = '-'
    if resolved_list:
        avg_resolution_days = round(sum(max((c.resolved_at - c.created_at).days, 1) for c in resolved_list) / len(resolved_list), 1)

    today = datetime.utcnow()
    monthly_labels, monthly_data = [], []
    for i in range(5, -1, -1):
        month = (today.month - i - 1) % 12 + 1
        year = today.year if today.month - i > 0 else today.year - 1
        count = sum(1 for c in complaints if c.created_at.month == month and c.created_at.year == year)
        monthly_labels.append(datetime(year, month, 1).strftime('%b %Y'))
        monthly_data.append(count)

    status_data = {}
    for s, label in Complaint.STATUSES:
        status_data[label] = sum(1 for c in complaints if c.status == s)

    cat_counter = {}
    pri_counter = {}
    district_counter = {}

    for c in complaints:
        cat_counter[c.get_category_label()] = cat_counter.get(c.get_category_label(), 0) + 1
        pri_counter[c.get_priority_label()] = pri_counter.get(c.get_priority_label(), 0) + 1
        district_name = (c.district.title() if c.district else 'Not specified')
        district_counter[district_name] = district_counter.get(district_name, 0) + 1

    cat_labels = list(cat_counter.keys())
    cat_values = list(cat_counter.values())
    pri_labels = list(pri_counter.keys())
    pri_values = list(pri_counter.values())
    district_labels = list(district_counter.keys())
    district_values = list(district_counter.values())

    resolution_rate = round((resolved_c / total_c * 100) if total_c else 0, 1)

    return render_template(
        'admin/reports.html',
        monthly_labels=monthly_labels,
        monthly_data=monthly_data,
        status_data=status_data,
        cat_labels=cat_labels,
        cat_values=cat_values,
        pri_labels=pri_labels,
        pri_values=pri_values,
        district_labels=district_labels,
        district_values=district_values,
        total_c=total_c,
        resolved_c=resolved_c,
        pending_c=pending_c,
        avg_resolution_days=avg_resolution_days,
        resolution_rate=resolution_rate,
        now=datetime.utcnow(),
        from_str=from_str,
        to_str=to_str
    )
