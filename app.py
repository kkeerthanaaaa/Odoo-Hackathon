"""
Dayflow HRMS: Human Resource Management System
Flask + SQLAlchemy + SQLite backend.

Roles (hierarchy): Admin -> CEO -> HR -> Manager -> Employee
See README.md for the full permission matrix.
"""
import os
from functools import wraps
from datetime import date, datetime, timedelta
from calendar import monthrange

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'hrms-lite-dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'hrms.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'

ROLES = ['Admin', 'CEO', 'HR', 'Manager', 'Employee']

# ---------------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='Employee')
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)
    is_active_account = db.Column(db.Boolean, default=True)
    created_on = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def is_active(self):
        return self.is_active_account


class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_archived = db.Column(db.Boolean, default=False)
    employees = db.relationship('Employee', backref='department', lazy=True)


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    designation = db.Column(db.String(100))
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    date_of_joining = db.Column(db.Date, default=date.today)
    gender = db.Column(db.String(10))
    employment_status = db.Column(db.String(20), default='Onboarding')
    is_archived = db.Column(db.Boolean, default=False)
    archived_on = db.Column(db.DateTime, nullable=True)
    reports_to = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)
    basic_salary = db.Column(db.Float, default=0.0)

    user = db.relationship('User', backref='employee', uselist=False, foreign_keys='User.employee_id')
    attendances = db.relationship('Attendance', backref='employee', lazy=True, cascade='all, delete-orphan',
                                   foreign_keys='Attendance.employee_id')
    leave_applications = db.relationship('LeaveApplication', backref='employee', lazy=True,
                                          cascade='all, delete-orphan',
                                          foreign_keys='LeaveApplication.employee_id')
    salary_slips = db.relationship('SalarySlip', backref='employee', lazy=True, cascade='all, delete-orphan')
    leave_balances = db.relationship('LeaveBalance', backref='employee', lazy=True, cascade='all, delete-orphan')
    manager = db.relationship('Employee', remote_side=[id], backref='direct_reports')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def status(self):
        return self.employment_status


class LeaveType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    default_days_per_year = db.Column(db.Integer, default=12)
    is_archived = db.Column(db.Boolean, default=False)


class LeaveBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_type.id'), nullable=False)
    year = db.Column(db.Integer, default=lambda: date.today().year)
    allocated = db.Column(db.Float, default=0.0)
    taken = db.Column(db.Float, default=0.0)

    leave_type = db.relationship('LeaveType')

    @property
    def remaining(self):
        return self.allocated - self.taken


class LeaveApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_type.id'), nullable=False)
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='Pending')
    manager_status = db.Column(db.String(20), default='NA')
    hr_status = db.Column(db.String(20), default='Pending')
    approver_stage = db.Column(db.String(20), default='hr')
    rejection_reason = db.Column(db.Text)
    applied_on = db.Column(db.DateTime, default=datetime.utcnow)
    decided_on = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)

    leave_type = db.relationship('LeaveType')

    @property
    def total_days(self):
        return (self.to_date - self.from_date).days + 1

    @property
    def is_final(self):
        return self.status in ('Approved', 'Rejected', 'Withdrawn', 'Cancelled')


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    att_date = db.Column(db.Date, default=date.today, nullable=False)
    check_in = db.Column(db.DateTime, nullable=True)
    check_out = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='Present')
    is_finalized = db.Column(db.Boolean, default=False)

    __table_args__ = (db.UniqueConstraint('employee_id', 'att_date', name='uix_emp_date'),)


class AttendanceCorrection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    att_date = db.Column(db.Date, nullable=False)
    requested_check_in = db.Column(db.String(10))
    requested_check_out = db.Column(db.String(10))
    requested_status = db.Column(db.String(20))
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='Pending')
    requested_on = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)
    reviewed_on = db.Column(db.DateTime, nullable=True)
    review_note = db.Column(db.Text)

    employee = db.relationship('Employee', foreign_keys=[employee_id],
                                backref=db.backref('attendance_corrections', cascade='all, delete-orphan'))


class SalaryStructure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    basic_percent = db.Column(db.Float, default=50.0)
    hra_percent = db.Column(db.Float, default=20.0)
    da_percent = db.Column(db.Float, default=10.0)
    pf_percent = db.Column(db.Float, default=12.0)
    professional_tax = db.Column(db.Float, default=200.0)


class SalarySlip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    basic = db.Column(db.Float, default=0.0)
    hra = db.Column(db.Float, default=0.0)
    da = db.Column(db.Float, default=0.0)
    gross_pay = db.Column(db.Float, default=0.0)
    pf_deduction = db.Column(db.Float, default=0.0)
    professional_tax = db.Column(db.Float, default=0.0)
    lop_days = db.Column(db.Float, default=0.0)
    total_deductions = db.Column(db.Float, default=0.0)
    net_pay = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='Generated')
    generated_on = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('employee_id', 'month', 'year', name='uix_emp_month_year'),)


class JobOpening(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='Open')
    posted_on = db.Column(db.Date, default=date.today)

    department = db.relationship('Department')
    applicants = db.relationship('JobApplicant', backref='job', lazy=True, cascade='all, delete-orphan')


class JobApplicant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_opening.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    status = db.Column(db.String(30), default='Applied')
    applied_on = db.Column(db.Date, default=date.today)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255))
    category = db.Column(db.String(30), default='info')
    is_read = db.Column(db.Boolean, default=False)
    created_on = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('notifications', cascade='all, delete-orphan'))


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender = db.Column(db.String(10), nullable=False)  # 'user' or 'bot'
    message = db.Column(db.Text, nullable=False)
    created_on = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('chat_messages', cascade='all, delete-orphan'))


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(80))
    role = db.Column(db.String(20))
    action = db.Column(db.String(255), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    target_repr = db.Column(db.String(150))
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# HELPERS: RBAC, AUDIT, NOTIFICATIONS
# ---------------------------------------------------------------------------

def log_action(action, target_type=None, target_id=None, target_repr=None, old=None, new=None):
    entry = AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        username=current_user.username if current_user.is_authenticated else 'system',
        role=current_user.role if current_user.is_authenticated else '',
        action=action, target_type=target_type, target_id=target_id, target_repr=target_repr,
        old_value=str(old) if old is not None else None,
        new_value=str(new) if new is not None else None,
    )
    db.session.add(entry)


def notify(user_id, message, link=None, category='info'):
    if not user_id:
        return
    db.session.add(Notification(user_id=user_id, message=message, link=link, category=category))


def notify_role(roles, message, link=None, category='info', exclude_user_id=None):
    users = User.query.filter(User.role.in_(roles), User.is_active_account == True).all()
    for u in users:
        if exclude_user_id and u.id == exclude_user_id:
            continue
        notify(u.id, message, link, category)


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                flash('You do not have permission to access that page.', 'danger')
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def is_admin(user=None):
    user = user or current_user
    return user.is_authenticated and user.role == 'Admin'


def is_hr(user=None):
    user = user or current_user
    return user.is_authenticated and user.role in ('Admin', 'HR')


def can_manage_employees(user=None):
    user = user or current_user
    return user.is_authenticated and user.role in ('Admin', 'HR')


def team_employee_ids(manager_employee_id):
    return [e.id for e in Employee.query.filter_by(reports_to=manager_employee_id, is_archived=False).all()]


def can_view_employee(emp, user=None):
    user = user or current_user
    if user.role in ('Admin', 'CEO', 'HR'):
        return True
    if user.role == 'Manager' and user.employee_id:
        return emp.id == user.employee_id or emp.reports_to == user.employee_id
    return user.employee_id == emp.id


def require_view_employee(emp):
    if not can_view_employee(emp):
        flash('You do not have permission to view that employee record.', 'danger')
        abort(403)


def leave_approval_chain(applicant_role, has_manager):
    if applicant_role == 'Employee' and has_manager:
        return 'Pending', 'NA', 'manager'
    return 'NA', 'Pending', 'hr'


@app.context_processor
def inject_globals():
    unread_count = 0
    if current_user.is_authenticated:
        unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return dict(is_hr=is_hr, is_admin=is_admin, can_manage_employees=can_manage_employees,
                current_user=current_user, date=date, unread_count=unread_count)


@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', code=403,
                            message="You don't have permission to access this page."), 403


@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404, message='Page not found.'), 404


# ---------------------------------------------------------------------------
# AUTH ROUTES
# ---------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and not user.is_active_account:
            flash('This account has been deactivated. Contact your administrator.', 'danger')
        elif user and user.check_password(password):
            login_user(user)
            log_action('User logged in', 'User', user.id, user.username)
            db.session.commit()
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    log_action('User logged out', 'User', current_user.id, current_user.username)
    db.session.commit()
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# DASHBOARD (role-specific)
# ---------------------------------------------------------------------------

@app.route('/')
@login_required
def dashboard():
    today = date.today()
    ctx = dict(today=today, role=current_user.role)

    my_attendance_today = None
    my_balances = []
    my_manager = None
    if current_user.employee_id:
        my_attendance_today = Attendance.query.filter_by(
            employee_id=current_user.employee_id, att_date=today).first()
        my_balances = LeaveBalance.query.filter_by(employee_id=current_user.employee_id, year=today.year).all()
        emp = Employee.query.get(current_user.employee_id)
        if emp and emp.reports_to:
            my_manager = Employee.query.get(emp.reports_to)
    ctx.update(my_attendance_today=my_attendance_today, my_balances=my_balances, my_manager=my_manager)

    if current_user.role in ('Admin', 'CEO'):
        ctx.update(
            total_employees=Employee.query.filter_by(is_archived=False).count(),
            active_employees=Employee.query.filter_by(is_archived=False, employment_status='Active').count(),
            total_departments=Department.query.filter_by(is_archived=False).count(),
            total_managers=Employee.query.join(User).filter(User.role == 'Manager').count(),
            total_hr=Employee.query.join(User).filter(User.role == 'HR').count(),
            pending_leaves=LeaveApplication.query.filter_by(status='Pending').count(),
            pending_corrections=AttendanceCorrection.query.filter_by(status='Pending').count(),
            present_today=Attendance.query.filter_by(att_date=today, status='Present').count(),
            payroll_total=db.session.query(db.func.coalesce(db.func.sum(SalarySlip.net_pay), 0)).filter(
                SalarySlip.year == today.year, SalarySlip.month == today.month).scalar(),
            dept_counts=db.session.query(Department.name, db.func.count(Employee.id)).
                outerjoin(Employee, db.and_(Employee.department_id == Department.id, Employee.is_archived == False)).
                filter(Department.is_archived == False).group_by(Department.id).all(),
            recent_activity=AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(8).all(),
            recent_leaves=LeaveApplication.query.order_by(LeaveApplication.applied_on.desc()).limit(6).all(),
        )
    elif current_user.role == 'HR':
        ctx.update(
            total_employees=Employee.query.filter_by(is_archived=False).count(),
            new_joiners=Employee.query.filter(Employee.is_archived == False,
                                               Employee.date_of_joining >= today - timedelta(days=30)).count(),
            on_leave_today=Attendance.query.filter_by(att_date=today, status='On Leave').count(),
            pending_leaves=LeaveApplication.query.filter(LeaveApplication.hr_status == 'Pending').count(),
            pending_corrections=AttendanceCorrection.query.filter_by(status='Pending').count(),
            dept_counts=db.session.query(Department.name, db.func.count(Employee.id)).
                outerjoin(Employee, db.and_(Employee.department_id == Department.id, Employee.is_archived == False)).
                filter(Department.is_archived == False).group_by(Department.id).all(),
            recent_leaves=LeaveApplication.query.order_by(LeaveApplication.applied_on.desc()).limit(6).all(),
        )
    elif current_user.role == 'Manager':
        my_team_ids = team_employee_ids(current_user.employee_id)
        ctx.update(
            team_size=len(my_team_ids),
            team_present_today=Attendance.query.filter(Attendance.employee_id.in_(my_team_ids or [-1]),
                                                         Attendance.att_date == today, Attendance.status == 'Present').count(),
            pending_team_leaves=LeaveApplication.query.filter(
                LeaveApplication.employee_id.in_(my_team_ids or [-1]), LeaveApplication.manager_status == 'Pending').count(),
            team_leaves=LeaveApplication.query.filter(LeaveApplication.employee_id.in_(my_team_ids or [-1])).
                order_by(LeaveApplication.applied_on.desc()).limit(6).all(),
            team=Employee.query.filter(Employee.id.in_(my_team_ids or [-1])).all(),
        )
    else:
        my_leaves = []
        if current_user.employee_id:
            my_leaves = LeaveApplication.query.filter_by(employee_id=current_user.employee_id).\
                order_by(LeaveApplication.applied_on.desc()).limit(5).all()
        ctx.update(my_leaves=my_leaves)
        recent = Attendance.query.filter_by(employee_id=current_user.employee_id).\
            order_by(Attendance.att_date.desc()).limit(6).all() if current_user.employee_id else []
        ctx.update(recent_attendance=recent)

    return render_template('dashboard.html', **ctx)


# ---------------------------------------------------------------------------
# PROFILE (self-service, any role)
# ---------------------------------------------------------------------------

@app.route('/profile')
@login_required
def my_profile():
    if not current_user.employee_id:
        flash('Your login is not linked to an employee record.', 'warning')
        return redirect(url_for('dashboard'))
    return redirect(url_for('employee_detail', emp_id=current_user.employee_id))


# ---------------------------------------------------------------------------
# EMPLOYEE ROUTES
# ---------------------------------------------------------------------------

@app.route('/employees')
@login_required
def employee_list():
    if current_user.role == 'Manager':
        return redirect(url_for('my_team'))
    if current_user.role == 'Employee':
        return redirect(url_for('my_profile'))
    q = request.args.get('q', '').strip()
    dept_filter = request.args.get('department', '')
    status_filter = request.args.get('status', '')
    show_archived = request.args.get('archived', '') == '1'

    query = Employee.query.filter_by(is_archived=show_archived)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            Employee.first_name.ilike(like), Employee.last_name.ilike(like),
            Employee.employee_code.ilike(like), Employee.email.ilike(like),
        ))
    if dept_filter:
        query = query.filter(Employee.department_id == dept_filter)
    if status_filter:
        query = query.filter(Employee.employment_status == status_filter)
    employees = query.order_by(Employee.id.desc()).all()
    departments = Department.query.filter_by(is_archived=False).all()
    return render_template('employees/list.html', employees=employees, q=q, departments=departments,
                            dept_filter=dept_filter, status_filter=status_filter, show_archived=show_archived)


@app.route('/my-team')
@login_required
@role_required('Manager')
def my_team():
    ids = team_employee_ids(current_user.employee_id)
    employees = Employee.query.filter(Employee.id.in_(ids or [-1])).order_by(Employee.first_name).all()
    return render_template('employees/list.html', employees=employees, q='', departments=[],
                            dept_filter='', status_filter='', show_archived=False, team_view=True)


@app.route('/employees/new', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'HR')
def employee_new():
    departments = Department.query.filter_by(is_archived=False).all()
    employees = Employee.query.filter_by(is_archived=False).all()
    if request.method == 'POST':
        f = request.form
        code = f.get('employee_code').strip()
        if Employee.query.filter_by(employee_code=code).first():
            flash('Employee code already exists.', 'danger')
            return render_template('employees/form.html', departments=departments, employees=employees, emp=None)
        if Employee.query.filter_by(email=f.get('email')).first():
            flash('An employee with this email already exists.', 'danger')
            return render_template('employees/form.html', departments=departments, employees=employees, emp=None)
        emp = Employee(
            employee_code=code, first_name=f.get('first_name'), last_name=f.get('last_name'),
            email=f.get('email'), phone=f.get('phone'), designation=f.get('designation'),
            department_id=f.get('department_id') or None,
            date_of_joining=datetime.strptime(f.get('date_of_joining'), '%Y-%m-%d').date() if f.get('date_of_joining') else date.today(),
            gender=f.get('gender'), reports_to=f.get('reports_to') or None,
            basic_salary=float(f.get('basic_salary') or 0),
            employment_status='Onboarding',
        )
        db.session.add(emp)
        db.session.commit()
        for lt in LeaveType.query.filter_by(is_archived=False).all():
            db.session.add(LeaveBalance(employee_id=emp.id, leave_type_id=lt.id,
                                         year=date.today().year, allocated=lt.default_days_per_year))
        log_action('Created employee', 'Employee', emp.id, emp.full_name)
        db.session.commit()
        flash(f'Employee {emp.full_name} created (Onboarding). Create a login for them from Users.', 'success')
        return redirect(url_for('employee_detail', emp_id=emp.id))
    return render_template('employees/form.html', departments=departments, employees=employees, emp=None)


@app.route('/employees/<int:emp_id>')
@login_required
def employee_detail(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    require_view_employee(emp)
    attendances = Attendance.query.filter_by(employee_id=emp.id).order_by(Attendance.att_date.desc()).limit(10).all()
    leaves = LeaveApplication.query.filter_by(employee_id=emp.id).order_by(LeaveApplication.applied_on.desc()).all()
    balances = LeaveBalance.query.filter_by(employee_id=emp.id, year=date.today().year).all()
    slips = SalarySlip.query.filter_by(employee_id=emp.id).order_by(SalarySlip.year.desc(), SalarySlip.month.desc()).all()
    manager = Employee.query.get(emp.reports_to) if emp.reports_to else None
    can_edit = can_manage_employees()
    is_self = current_user.employee_id == emp.id
    return render_template('employees/detail.html', emp=emp, attendances=attendances,
                            leaves=leaves, balances=balances, slips=slips, manager=manager,
                            can_edit=can_edit, is_self=is_self,
                            show_payroll=(can_edit or current_user.role in ('CEO',) or is_self))


@app.route('/employees/<int:emp_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'HR')
def employee_edit(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    departments = Department.query.filter_by(is_archived=False).all()
    employees = Employee.query.filter(Employee.id != emp_id, Employee.is_archived == False).all()
    if request.method == 'POST':
        f = request.form
        old = f"{emp.full_name}, {emp.designation}, status={emp.employment_status}"
        emp.first_name = f.get('first_name')
        emp.last_name = f.get('last_name')
        emp.email = f.get('email')
        emp.phone = f.get('phone')
        emp.designation = f.get('designation')
        emp.department_id = f.get('department_id') or None
        emp.gender = f.get('gender')
        new_status = f.get('employment_status') or emp.employment_status
        new_manager = f.get('reports_to') or None
        emp.employment_status = new_status
        emp.reports_to = new_manager
        emp.basic_salary = float(f.get('basic_salary') or 0)
        db.session.commit()
        log_action('Updated employee', 'Employee', emp.id, emp.full_name, old=old,
                   new=f"{emp.full_name}, {emp.designation}, status={emp.employment_status}")
        if emp.user:
            notify(emp.user.id, 'Your profile information was updated by HR.', url_for('employee_detail', emp_id=emp.id))
        db.session.commit()
        flash('Employee updated.', 'success')
        return redirect(url_for('employee_detail', emp_id=emp.id))
    return render_template('employees/form.html', departments=departments, employees=employees, emp=emp)


@app.route('/employees/<int:emp_id>/set-status', methods=['POST'])
@login_required
@role_required('Admin', 'HR')
def employee_set_status(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    new_status = request.form.get('employment_status')
    if new_status not in ('Onboarding', 'Active', 'On Leave', 'Notice Period', 'Inactive', 'Exited'):
        flash('Invalid status.', 'danger')
        return redirect(url_for('employee_detail', emp_id=emp_id))
    old = emp.employment_status
    emp.employment_status = new_status
    log_action(f'Changed employment status', 'Employee', emp.id, emp.full_name, old=old, new=new_status)
    if emp.user:
        notify(emp.user.id, f'Your employment status changed to "{new_status}".', url_for('employee_detail', emp_id=emp.id))
    db.session.commit()
    flash(f'{emp.full_name} status set to {new_status}.', 'success')
    return redirect(url_for('employee_detail', emp_id=emp_id))


@app.route('/employees/<int:emp_id>/archive', methods=['POST'])
@login_required
@role_required('Admin', 'HR')
def employee_archive(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    emp.is_archived = True
    emp.archived_on = datetime.utcnow()
    if emp.user:
        emp.user.is_active_account = False
    log_action('Archived employee', 'Employee', emp.id, emp.full_name)
    db.session.commit()
    flash(f'{emp.full_name} archived. Their record and history are preserved and can be restored.', 'info')
    return redirect(url_for('employee_list'))


@app.route('/employees/<int:emp_id>/restore', methods=['POST'])
@login_required
@role_required('Admin', 'HR')
def employee_restore(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    emp.is_archived = False
    emp.archived_on = None
    log_action('Restored employee', 'Employee', emp.id, emp.full_name)
    db.session.commit()
    flash(f'{emp.full_name} restored.', 'success')
    return redirect(url_for('employee_list', archived=1))


@app.route('/employees/<int:emp_id>/delete', methods=['POST'])
@login_required
@role_required('Admin')
def employee_delete(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    if not emp.is_archived:
        flash('Archive the employee before permanent deletion.', 'warning')
        return redirect(url_for('employee_detail', emp_id=emp_id))
    name = emp.full_name
    if emp.user:
        db.session.delete(emp.user)
    db.session.delete(emp)
    log_action('Permanently deleted employee', 'Employee', emp_id, name)
    db.session.commit()
    flash(f'{name} permanently deleted.', 'info')
    return redirect(url_for('employee_list', archived=1))


# ---------------------------------------------------------------------------
# DEPARTMENT ROUTES
# ---------------------------------------------------------------------------

@app.route('/departments', methods=['GET', 'POST'])
@login_required
def department_list():
    if request.method == 'POST':
        if current_user.role not in ('Admin', 'HR'):
            flash('You do not have permission to manage departments.', 'danger')
            abort(403)
        name = request.form.get('name', '').strip()
        if name and not Department.query.filter_by(name=name).first():
            d = Department(name=name)
            db.session.add(d)
            db.session.commit()
            log_action('Created department', 'Department', d.id, d.name)
            db.session.commit()
            flash('Department added.', 'success')
        else:
            flash('Department name is empty or already exists.', 'danger')
        return redirect(url_for('department_list'))
    departments = Department.query.filter_by(is_archived=False).all()
    archived = Department.query.filter_by(is_archived=True).all()
    return render_template('departments.html', departments=departments, archived=archived)


@app.route('/departments/<int:dept_id>/archive', methods=['POST'])
@login_required
@role_required('Admin', 'HR')
def department_archive(dept_id):
    dept = Department.query.get_or_404(dept_id)
    dept.is_archived = True
    log_action('Archived department', 'Department', dept.id, dept.name)
    db.session.commit()
    flash('Department archived.', 'info')
    return redirect(url_for('department_list'))


@app.route('/departments/<int:dept_id>/restore', methods=['POST'])
@login_required
@role_required('Admin', 'HR')
def department_restore(dept_id):
    dept = Department.query.get_or_404(dept_id)
    dept.is_archived = False
    log_action('Restored department', 'Department', dept.id, dept.name)
    db.session.commit()
    flash('Department restored.', 'success')
    return redirect(url_for('department_list'))


@app.route('/departments/<int:dept_id>/delete', methods=['POST'])
@login_required
@role_required('Admin')
def department_delete(dept_id):
    dept = Department.query.get_or_404(dept_id)
    if Employee.query.filter_by(department_id=dept.id).count() > 0:
        flash('Cannot delete a department that has employees. Reassign or archive instead.', 'danger')
        return redirect(url_for('department_list'))
    name = dept.name
    db.session.delete(dept)
    log_action('Deleted department', 'Department', dept_id, name)
    db.session.commit()
    flash('Department deleted.', 'info')
    return redirect(url_for('department_list'))


# ---------------------------------------------------------------------------
# ATTENDANCE ROUTES
# ---------------------------------------------------------------------------

@app.route('/attendance')
@login_required
def attendance_list():
    sel_date = request.args.get('date', date.today().isoformat())
    d = datetime.strptime(sel_date, '%Y-%m-%d').date()

    if current_user.role in ('Admin', 'CEO', 'HR'):
        scope_ids = None
    elif current_user.role == 'Manager':
        scope_ids = team_employee_ids(current_user.employee_id) + ([current_user.employee_id] if current_user.employee_id else [])
    else:
        scope_ids = [current_user.employee_id] if current_user.employee_id else [-1]

    q = Attendance.query.filter_by(att_date=d)
    if scope_ids is not None:
        q = q.filter(Attendance.employee_id.in_(scope_ids or [-1]))
    records = q.all()
    marked_ids = {r.employee_id for r in records}

    emp_q = Employee.query.filter_by(employment_status='Active', is_archived=False)
    if scope_ids is not None:
        emp_q = emp_q.filter(Employee.id.in_(scope_ids or [-1]))
    unmarked = [e for e in emp_q.all() if e.id not in marked_ids]

    my_corrections = []
    if current_user.employee_id:
        my_corrections = AttendanceCorrection.query.filter_by(employee_id=current_user.employee_id).\
            order_by(AttendanceCorrection.requested_on.desc()).limit(10).all()

    pending_corrections = []
    if current_user.role in ('Admin', 'HR', 'Manager'):
        cq = AttendanceCorrection.query.filter_by(status='Pending')
        if current_user.role == 'Manager':
            ids = team_employee_ids(current_user.employee_id)
            cq = cq.filter(AttendanceCorrection.employee_id.in_(ids or [-1]))
        pending_corrections = cq.order_by(AttendanceCorrection.requested_on.desc()).all()

    return render_template('attendance.html', records=records, unmarked=unmarked, sel_date=sel_date,
                            my_corrections=my_corrections, pending_corrections=pending_corrections,
                            can_mark=current_user.role in ('Admin', 'HR', 'Manager'))


@app.route('/attendance/checkin', methods=['POST'])
@login_required
def attendance_checkin():
    if not current_user.employee_id:
        flash('Your login is not linked to an employee record.', 'danger')
        return redirect(url_for('dashboard'))
    today = date.today()
    record = Attendance.query.filter_by(employee_id=current_user.employee_id, att_date=today).first()
    if record and record.check_in:
        flash('You have already checked in today.', 'warning')
    else:
        if not record:
            record = Attendance(employee_id=current_user.employee_id, att_date=today, status='Present')
            db.session.add(record)
        record.check_in = datetime.now()
        record.status = 'Present'
        db.session.commit()
        flash('Checked in successfully.', 'success')
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/attendance/checkout', methods=['POST'])
@login_required
def attendance_checkout():
    if not current_user.employee_id:
        flash('Your login is not linked to an employee record.', 'danger')
        return redirect(url_for('dashboard'))
    today = date.today()
    record = Attendance.query.filter_by(employee_id=current_user.employee_id, att_date=today).first()
    if not record or not record.check_in:
        flash('You need to check in first.', 'warning')
    elif record.check_out:
        flash('You have already checked out today.', 'warning')
    else:
        record.check_out = datetime.now()
        db.session.commit()
        flash('Checked out successfully.', 'success')
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/attendance/mark', methods=['POST'])
@login_required
@role_required('Admin', 'HR', 'Manager')
def attendance_mark():
    emp_id = int(request.form.get('employee_id'))
    if current_user.role == 'Manager' and emp_id not in team_employee_ids(current_user.employee_id):
        flash('You can only mark attendance for your own team.', 'danger')
        return redirect(url_for('attendance_list'))
    status = request.form.get('status')
    sel_date = request.form.get('att_date')
    d = datetime.strptime(sel_date, '%Y-%m-%d').date()
    record = Attendance.query.filter_by(employee_id=emp_id, att_date=d).first()
    if not record:
        record = Attendance(employee_id=emp_id, att_date=d)
        db.session.add(record)
    record.status = status
    record.is_finalized = True
    log_action('Marked attendance', 'Attendance', record.id, f'{d} = {status}')
    db.session.commit()
    flash('Attendance marked.', 'success')
    return redirect(url_for('attendance_list', date=sel_date))


@app.route('/attendance/correction/request', methods=['POST'])
@login_required
def attendance_correction_request():
    if not current_user.employee_id:
        flash('Your login is not linked to an employee record.', 'danger')
        return redirect(url_for('attendance_list'))
    f = request.form
    att_date = datetime.strptime(f.get('att_date'), '%Y-%m-%d').date()
    corr = AttendanceCorrection(
        employee_id=current_user.employee_id, att_date=att_date,
        requested_check_in=f.get('requested_check_in') or None,
        requested_check_out=f.get('requested_check_out') or None,
        requested_status=f.get('requested_status') or None,
        reason=f.get('reason'),
    )
    db.session.add(corr)
    db.session.commit()
    log_action('Requested attendance correction', 'AttendanceCorrection', corr.id, str(att_date))
    emp = Employee.query.get(current_user.employee_id)
    if emp.reports_to:
        mgr = Employee.query.get(emp.reports_to)
        if mgr and mgr.user:
            notify(mgr.user.id, f'{emp.full_name} requested an attendance correction for {att_date}.',
                   url_for('attendance_list'))
    notify_role(['HR'], f'{emp.full_name} requested an attendance correction for {att_date}.', url_for('attendance_list'))
    db.session.commit()
    flash('Correction request submitted for approval.', 'success')
    return redirect(url_for('attendance_list'))


@app.route('/attendance/correction/<int:corr_id>/<action>', methods=['POST'])
@login_required
@role_required('Admin', 'HR', 'Manager')
def attendance_correction_review(corr_id, action):
    corr = AttendanceCorrection.query.get_or_404(corr_id)
    if current_user.role == 'Manager' and corr.employee_id not in team_employee_ids(current_user.employee_id):
        flash('You can only review requests from your own team.', 'danger')
        return redirect(url_for('attendance_list'))
    if action not in ('approve', 'reject'):
        abort(404)
    corr.status = 'Approved' if action == 'approve' else 'Rejected'
    corr.reviewed_by = current_user.employee_id
    corr.reviewed_on = datetime.utcnow()
    corr.review_note = request.form.get('review_note', '')
    if corr.status == 'Approved':
        record = Attendance.query.filter_by(employee_id=corr.employee_id, att_date=corr.att_date).first()
        if not record:
            record = Attendance(employee_id=corr.employee_id, att_date=corr.att_date)
            db.session.add(record)
        if corr.requested_status:
            record.status = corr.requested_status
        if corr.requested_check_in:
            record.check_in = datetime.combine(corr.att_date, datetime.strptime(corr.requested_check_in, '%H:%M').time())
        if corr.requested_check_out:
            record.check_out = datetime.combine(corr.att_date, datetime.strptime(corr.requested_check_out, '%H:%M').time())
        record.is_finalized = True
    log_action(f'{corr.status} attendance correction', 'AttendanceCorrection', corr.id, str(corr.att_date))
    emp = Employee.query.get(corr.employee_id)
    if emp and emp.user:
        notify(emp.user.id, f'Your attendance correction for {corr.att_date} was {corr.status.lower()}.',
               url_for('attendance_list'))
    db.session.commit()
    flash(f'Correction request {corr.status.lower()}.', 'success')
    return redirect(url_for('attendance_list'))


# ---------------------------------------------------------------------------
# LEAVE MANAGEMENT ROUTES
# ---------------------------------------------------------------------------

@app.route('/leaves')
@login_required
def leave_list():
    if current_user.role in ('Admin', 'CEO', 'HR'):
        leaves = LeaveApplication.query.order_by(LeaveApplication.applied_on.desc()).all()
    elif current_user.role == 'Manager':
        ids = team_employee_ids(current_user.employee_id) + ([current_user.employee_id] if current_user.employee_id else [])
        leaves = LeaveApplication.query.filter(LeaveApplication.employee_id.in_(ids or [-1])).\
            order_by(LeaveApplication.applied_on.desc()).all()
    else:
        leaves = LeaveApplication.query.filter_by(employee_id=current_user.employee_id).\
            order_by(LeaveApplication.applied_on.desc()).all()

    pending_for_me = []
    if current_user.role == 'Manager':
        ids = team_employee_ids(current_user.employee_id)
        pending_for_me = LeaveApplication.query.filter(
            LeaveApplication.employee_id.in_(ids or [-1]), LeaveApplication.manager_status == 'Pending').all()
    elif current_user.role in ('Admin', 'HR'):
        pending_for_me = LeaveApplication.query.filter(LeaveApplication.hr_status == 'Pending',
                                                         LeaveApplication.approver_stage == 'hr').all()
    elif current_user.role == 'CEO':
        pending_for_me = LeaveApplication.query.filter(LeaveApplication.hr_status == 'Pending',
                                                         LeaveApplication.approver_stage == 'hr').join(
            Employee, LeaveApplication.employee_id == Employee.id).join(
            User, User.employee_id == Employee.id).filter(User.role.in_(['Manager', 'HR'])).all()

    return render_template('leaves/list.html', leaves=leaves, pending_for_me=pending_for_me)


@app.route('/leaves/apply', methods=['GET', 'POST'])
@login_required
def leave_apply():
    if not current_user.employee_id:
        flash('Your login is not linked to an employee record.', 'danger')
        return redirect(url_for('dashboard'))
    leave_types = LeaveType.query.filter_by(is_archived=False).all()
    balances = {b.leave_type_id: b.remaining for b in
                LeaveBalance.query.filter_by(employee_id=current_user.employee_id, year=date.today().year).all()}
    if request.method == 'POST':
        f = request.form
        from_date = datetime.strptime(f.get('from_date'), '%Y-%m-%d').date()
        to_date = datetime.strptime(f.get('to_date'), '%Y-%m-%d').date()
        if to_date < from_date:
            flash('To Date cannot be before From Date.', 'danger')
        elif from_date < date.today():
            flash('From Date cannot be in the past.', 'danger')
        else:
            emp = Employee.query.get(current_user.employee_id)
            mgr_status, hr_status, stage = leave_approval_chain(current_user.role, bool(emp.reports_to))
            leave = LeaveApplication(
                employee_id=current_user.employee_id, leave_type_id=f.get('leave_type_id'),
                from_date=from_date, to_date=to_date, reason=f.get('reason'),
                status='Pending', manager_status=mgr_status, hr_status=hr_status, approver_stage=stage,
            )
            db.session.add(leave)
            db.session.commit()
            log_action('Applied for leave', 'LeaveApplication', leave.id, f'{emp.full_name} {from_date}..{to_date}')
            if stage == 'manager' and emp.reports_to:
                mgr = Employee.query.get(emp.reports_to)
                if mgr and mgr.user:
                    notify(mgr.user.id, f'{emp.full_name} applied for {leave.leave_type.name} ({from_date} to {to_date}).',
                           url_for('leave_list'))
            else:
                notify_role(['HR'] if current_user.role == 'Employee' else ['Admin', 'CEO'],
                            f'{emp.full_name} applied for {leave.leave_type.name} ({from_date} to {to_date}).',
                            url_for('leave_list'))
            db.session.commit()
            flash('Leave application submitted.', 'success')
            return redirect(url_for('leave_list'))
    return render_template('leaves/apply.html', leave_types=leave_types, balances=balances)


@app.route('/leaves/<int:leave_id>/edit', methods=['GET', 'POST'])
@login_required
def leave_edit(leave_id):
    leave = LeaveApplication.query.get_or_404(leave_id)
    if leave.employee_id != current_user.employee_id:
        flash('You can only edit your own leave requests.', 'danger')
        abort(403)
    if leave.status != 'Pending':
        flash('Only pending leave requests can be edited.', 'warning')
        return redirect(url_for('leave_list'))
    leave_types = LeaveType.query.filter_by(is_archived=False).all()
    balances = {b.leave_type_id: b.remaining for b in
                LeaveBalance.query.filter_by(employee_id=current_user.employee_id, year=date.today().year).all()}
    if request.method == 'POST':
        f = request.form
        from_date = datetime.strptime(f.get('from_date'), '%Y-%m-%d').date()
        to_date = datetime.strptime(f.get('to_date'), '%Y-%m-%d').date()
        if to_date < from_date:
            flash('To Date cannot be before From Date.', 'danger')
        else:
            leave.leave_type_id = f.get('leave_type_id')
            leave.from_date = from_date
            leave.to_date = to_date
            leave.reason = f.get('reason')
            log_action('Edited pending leave', 'LeaveApplication', leave.id, f'{from_date}..{to_date}')
            db.session.commit()
            flash('Leave request updated.', 'success')
            return redirect(url_for('leave_list'))
    return render_template('leaves/apply.html', leave_types=leave_types, balances=balances, leave=leave, editing=True)


@app.route('/leaves/<int:leave_id>/withdraw', methods=['POST'])
@login_required
def leave_withdraw(leave_id):
    leave = LeaveApplication.query.get_or_404(leave_id)
    if leave.employee_id != current_user.employee_id:
        flash('You can only withdraw your own leave requests.', 'danger')
        abort(403)
    if leave.status != 'Pending':
        flash('Only pending leave requests can be withdrawn.', 'warning')
        return redirect(url_for('leave_list'))
    leave.status = 'Withdrawn'
    leave.decided_on = datetime.utcnow()
    log_action('Withdrew leave request', 'LeaveApplication', leave.id, leave.employee.full_name)
    db.session.commit()
    flash('Leave request withdrawn.', 'info')
    return redirect(url_for('leave_list'))


@app.route('/leaves/<int:leave_id>/cancel', methods=['POST'])
@login_required
def leave_cancel(leave_id):
    leave = LeaveApplication.query.get_or_404(leave_id)
    if leave.employee_id != current_user.employee_id:
        flash('You can only cancel your own leave.', 'danger')
        abort(403)
    if leave.status != 'Approved' or leave.from_date < date.today():
        flash('Only upcoming approved leave can be cancelled.', 'warning')
        return redirect(url_for('leave_list'))
    leave.status = 'Cancelled'
    bal = LeaveBalance.query.filter_by(employee_id=leave.employee_id, leave_type_id=leave.leave_type_id,
                                        year=leave.from_date.year).first()
    if bal:
        bal.taken = max(0, bal.taken - leave.total_days)
    d = leave.from_date
    while d <= leave.to_date:
        att = Attendance.query.filter_by(employee_id=leave.employee_id, att_date=d).first()
        if att and att.status == 'On Leave':
            att.status = 'Present' if d < date.today() else 'Absent'
        d += timedelta(days=1)
    log_action('Cancelled approved leave', 'LeaveApplication', leave.id, leave.employee.full_name)
    db.session.commit()
    flash('Leave cancelled and balance restored.', 'info')
    return redirect(url_for('leave_list'))


@app.route('/leaves/<int:leave_id>/<action>', methods=['POST'])
@login_required
def leave_action(leave_id, action):
    leave = LeaveApplication.query.get_or_404(leave_id)
    if action not in ('approve', 'reject'):
        flash('Invalid action.', 'danger')
        return redirect(url_for('leave_list'))

    if leave.approver_stage == 'manager':
        ids = team_employee_ids(current_user.employee_id) if current_user.employee_id else []
        if current_user.role != 'Manager' or leave.employee_id not in ids:
            flash("Only the employee's manager can act on this request at this stage.", 'danger')
            abort(403)
        leave.manager_status = 'Approved' if action == 'approve' else 'Rejected'
        if action == 'reject':
            leave.status = 'Rejected'
            leave.rejection_reason = request.form.get('reason', '')
            leave.decided_on = datetime.utcnow()
        else:
            leave.approver_stage = 'hr'
            leave.hr_status = 'Pending'
            notify_role(['HR'], f"{leave.employee.full_name}'s leave was approved by manager and needs HR review.",
                       url_for('leave_list'))
    elif leave.approver_stage == 'hr':
        allowed = current_user.role in ('Admin', 'HR') or (
            current_user.role == 'CEO' and leave.employee.user and leave.employee.user.role in ('Manager', 'HR'))
        if not allowed:
            flash('You are not authorized to act on this request.', 'danger')
            abort(403)
        leave.hr_status = 'Approved' if action == 'approve' else 'Rejected'
        leave.status = 'Approved' if action == 'approve' else 'Rejected'
        if action == 'reject':
            leave.rejection_reason = request.form.get('reason', '')
        leave.decided_on = datetime.utcnow()
    else:
        flash('This request has already been finalized.', 'warning')
        return redirect(url_for('leave_list'))

    leave.reviewed_by = current_user.employee_id

    if leave.status == 'Approved':
        bal = LeaveBalance.query.filter_by(employee_id=leave.employee_id,
                                            leave_type_id=leave.leave_type_id, year=leave.from_date.year).first()
        if bal:
            bal.taken += leave.total_days
        d = leave.from_date
        while d <= leave.to_date:
            att = Attendance.query.filter_by(employee_id=leave.employee_id, att_date=d).first()
            if not att:
                att = Attendance(employee_id=leave.employee_id, att_date=d)
                db.session.add(att)
            att.status = 'On Leave'
            d += timedelta(days=1)

    log_action(f'Leave {leave.status if leave.status != "Pending" else action}', 'LeaveApplication',
               leave.id, leave.employee.full_name)
    if leave.employee.user:
        stage_msg = 'moved to the next approval stage' if leave.status == 'Pending' else leave.status.lower()
        notify(leave.employee.user.id, f'Your leave request ({leave.from_date} to {leave.to_date}) was {stage_msg}.',
               url_for('leave_list'))
    db.session.commit()
    flash('Leave application updated.', 'success')
    return redirect(url_for('leave_list'))


@app.route('/leave-types', methods=['GET', 'POST'])
@login_required
def leave_type_list():
    if request.method == 'POST':
        if current_user.role not in ('Admin', 'HR'):
            abort(403)
        name = request.form.get('name', '').strip()
        days = int(request.form.get('default_days_per_year') or 12)
        if name and not LeaveType.query.filter_by(name=name).first():
            lt = LeaveType(name=name, default_days_per_year=days)
            db.session.add(lt)
            db.session.commit()
            log_action('Created leave type', 'LeaveType', lt.id, lt.name)
            db.session.commit()
            flash('Leave type added.', 'success')
        else:
            flash('Leave type is empty or already exists.', 'danger')
        return redirect(url_for('leave_type_list'))
    leave_types = LeaveType.query.filter_by(is_archived=False).all()
    archived = LeaveType.query.filter_by(is_archived=True).all()
    return render_template('leave_types.html', leave_types=leave_types, archived=archived)


@app.route('/leave-types/<int:lt_id>/archive', methods=['POST'])
@login_required
@role_required('Admin', 'HR')
def leave_type_archive(lt_id):
    lt = LeaveType.query.get_or_404(lt_id)
    lt.is_archived = True
    log_action('Archived leave type', 'LeaveType', lt.id, lt.name)
    db.session.commit()
    flash('Leave type archived.', 'info')
    return redirect(url_for('leave_type_list'))


@app.route('/leave-types/<int:lt_id>/restore', methods=['POST'])
@login_required
@role_required('Admin', 'HR')
def leave_type_restore(lt_id):
    lt = LeaveType.query.get_or_404(lt_id)
    lt.is_archived = False
    log_action('Restored leave type', 'LeaveType', lt.id, lt.name)
    db.session.commit()
    flash('Leave type restored.', 'success')
    return redirect(url_for('leave_type_list'))


# ---------------------------------------------------------------------------
# PAYROLL ROUTES
# ---------------------------------------------------------------------------

@app.route('/payroll')
@login_required
def payroll_home():
    if current_user.role in ('Admin', 'CEO', 'HR'):
        slips = SalarySlip.query.order_by(SalarySlip.year.desc(), SalarySlip.month.desc()).all()
    elif current_user.role == 'Manager':
        ids = team_employee_ids(current_user.employee_id) + ([current_user.employee_id] if current_user.employee_id else [])
        slips = SalarySlip.query.filter(SalarySlip.employee_id.in_(ids or [-1])).\
            order_by(SalarySlip.year.desc(), SalarySlip.month.desc()).all()
    else:
        slips = SalarySlip.query.filter_by(employee_id=current_user.employee_id).\
            order_by(SalarySlip.year.desc(), SalarySlip.month.desc()).all()
    structure = SalaryStructure.query.first()
    employees = Employee.query.filter_by(employment_status='Active', is_archived=False).all()
    return render_template('payroll/list.html', slips=slips, structure=structure, employees=employees)


@app.route('/payroll/generate', methods=['POST'])
@login_required
@role_required('Admin', 'HR')
def payroll_generate():
    month = int(request.form.get('month'))
    year = int(request.form.get('year'))
    structure = SalaryStructure.query.first()
    if not structure:
        structure = SalaryStructure(name='Standard')
        db.session.add(structure)
        db.session.commit()

    days_in_month = monthrange(year, month)[1]
    generated = 0
    for emp in Employee.query.filter_by(employment_status='Active', is_archived=False).all():
        existing = SalarySlip.query.filter_by(employee_id=emp.id, month=month, year=year).first()
        if existing:
            continue
        start = date(year, month, 1)
        end = date(year, month, days_in_month)
        absent_days = Attendance.query.filter(
            Attendance.employee_id == emp.id, Attendance.att_date >= start,
            Attendance.att_date <= end, Attendance.status == 'Absent').count()

        ctc_monthly = emp.basic_salary
        basic = round(ctc_monthly * structure.basic_percent / 100, 2)
        hra = round(basic * structure.hra_percent / 100, 2)
        da = round(basic * structure.da_percent / 100, 2)
        gross = round(basic + hra + da, 2)
        per_day = gross / days_in_month if days_in_month else 0
        lop_deduction = round(per_day * absent_days, 2)
        pf = round(basic * structure.pf_percent / 100, 2)
        total_deductions = round(pf + structure.professional_tax + lop_deduction, 2)
        net_pay = round(gross - total_deductions, 2)

        slip = SalarySlip(employee_id=emp.id, month=month, year=year, basic=basic, hra=hra, da=da,
                           gross_pay=gross, pf_deduction=pf, professional_tax=structure.professional_tax,
                           lop_days=absent_days, total_deductions=total_deductions, net_pay=net_pay)
        db.session.add(slip)
        db.session.flush()
        if emp.user:
            notify(emp.user.id, f'Your salary slip for {month}/{year} is available.', url_for('payroll_home'))
        generated += 1
    log_action(f'Generated payroll for {month}/{year}', 'SalarySlip', None, f'{generated} slips')
    db.session.commit()
    flash(f'Generated {generated} salary slip(s) for {month}/{year}.', 'success')
    return redirect(url_for('payroll_home'))


@app.route('/payroll/structure', methods=['POST'])
@login_required
@role_required('Admin', 'HR')
def payroll_structure_update():
    structure = SalaryStructure.query.first()
    if not structure:
        structure = SalaryStructure(name='Standard')
        db.session.add(structure)
    f = request.form
    structure.basic_percent = float(f.get('basic_percent'))
    structure.hra_percent = float(f.get('hra_percent'))
    structure.da_percent = float(f.get('da_percent'))
    structure.pf_percent = float(f.get('pf_percent'))
    structure.professional_tax = float(f.get('professional_tax'))
    log_action('Updated salary structure', 'SalaryStructure', structure.id, structure.name)
    db.session.commit()
    flash('Salary structure updated.', 'success')
    return redirect(url_for('payroll_home'))


@app.route('/payroll/slip/<int:slip_id>')
@login_required
def payroll_slip_detail(slip_id):
    slip = SalarySlip.query.get_or_404(slip_id)
    if not (current_user.role in ('Admin', 'CEO', 'HR') or current_user.employee_id == slip.employee_id or
            (current_user.role == 'Manager' and slip.employee_id in team_employee_ids(current_user.employee_id))):
        abort(403)
    return render_template('payroll/slip.html', slip=slip)


# ---------------------------------------------------------------------------
# RECRUITMENT ROUTES
# ---------------------------------------------------------------------------

@app.route('/recruitment')
@login_required
def recruitment_list():
    jobs = JobOpening.query.order_by(JobOpening.posted_on.desc()).all()
    departments = Department.query.filter_by(is_archived=False).all()
    return render_template('recruitment/list.html', jobs=jobs, departments=departments)


@app.route('/recruitment/new', methods=['POST'])
@login_required
@role_required('Admin', 'HR')
def job_new():
    f = request.form
    job = JobOpening(title=f.get('title'), department_id=f.get('department_id') or None,
                      description=f.get('description'))
    db.session.add(job)
    db.session.commit()
    log_action('Posted job opening', 'JobOpening', job.id, job.title)
    db.session.commit()
    flash('Job opening posted.', 'success')
    return redirect(url_for('recruitment_list'))


@app.route('/recruitment/<int:job_id>')
@login_required
def job_detail(job_id):
    job = JobOpening.query.get_or_404(job_id)
    return render_template('recruitment/detail.html', job=job)


@app.route('/recruitment/<int:job_id>/apply', methods=['POST'])
@login_required
@role_required('Admin', 'HR')
def job_apply(job_id):
    job = JobOpening.query.get_or_404(job_id)
    f = request.form
    applicant = JobApplicant(job_id=job.id, name=f.get('name'), email=f.get('email'), phone=f.get('phone'))
    db.session.add(applicant)
    db.session.commit()
    flash('Applicant added.', 'success')
    return redirect(url_for('job_detail', job_id=job.id))


@app.route('/recruitment/applicant/<int:app_id>/status', methods=['POST'])
@login_required
@role_required('Admin', 'HR')
def applicant_status(app_id):
    applicant = JobApplicant.query.get_or_404(app_id)
    applicant.status = request.form.get('status')
    db.session.commit()
    flash('Applicant status updated.', 'success')
    return redirect(url_for('job_detail', job_id=applicant.job_id))


@app.route('/recruitment/<int:job_id>/close', methods=['POST'])
@login_required
@role_required('Admin', 'HR')
def job_close(job_id):
    job = JobOpening.query.get_or_404(job_id)
    job.status = 'Closed' if job.status == 'Open' else 'Open'
    log_action('Toggled job opening status', 'JobOpening', job.id, job.title, new=job.status)
    db.session.commit()
    return redirect(url_for('recruitment_list'))


# ---------------------------------------------------------------------------
# USER / ACCOUNT MANAGEMENT (Admin only)
# ---------------------------------------------------------------------------

@app.route('/users', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def user_list():
    employees = Employee.query.filter(~Employee.id.in_(
        db.session.query(User.employee_id).filter(User.employee_id.isnot(None))
    ), Employee.is_archived == False).all()
    if request.method == 'POST':
        f = request.form
        if User.query.filter_by(username=f.get('username')).first():
            flash('Username already taken.', 'danger')
        elif User.query.filter_by(email=f.get('email')).first():
            flash('Email already in use.', 'danger')
        else:
            user = User(username=f.get('username'), email=f.get('email'),
                        role=f.get('role'), employee_id=f.get('employee_id') or None)
            user.set_password(f.get('password'))
            db.session.add(user)
            db.session.commit()
            if user.employee_id:
                emp = Employee.query.get(user.employee_id)
                if emp.employment_status == 'Onboarding':
                    emp.employment_status = 'Active'
            log_action('Created user account', 'User', user.id, user.username, new=user.role)
            db.session.commit()
            flash('User account created.', 'success')
        return redirect(url_for('user_list'))
    users = User.query.order_by(User.id.desc()).all()
    return render_template('users.html', users=users, employees=employees, roles=ROLES)


@app.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@role_required('Admin')
def user_toggle_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('user_list'))
    user.is_active_account = not user.is_active_account
    log_action('Toggled user active state', 'User', user.id, user.username, new=user.is_active_account)
    db.session.commit()
    flash(f'{user.username} {"activated" if user.is_active_account else "deactivated"}.', 'success')
    return redirect(url_for('user_list'))


@app.route('/users/<int:user_id>/role', methods=['POST'])
@login_required
@role_required('Admin')
def user_change_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    if new_role not in ROLES:
        flash('Invalid role.', 'danger')
        return redirect(url_for('user_list'))
    old_role = user.role
    user.role = new_role
    log_action('Changed user role', 'User', user.id, user.username, old=old_role, new=new_role)
    notify(user.id, f'Your account role was changed to {new_role}.')
    db.session.commit()
    flash(f"{user.username}'s role changed to {new_role}.", 'success')
    return redirect(url_for('user_list'))


@app.route('/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@role_required('Admin')
def user_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 6:
        flash('Password must be at least 6 characters.', 'danger')
        return redirect(url_for('user_list'))
    user.set_password(new_password)
    log_action('Reset user password', 'User', user.id, user.username)
    notify(user.id, 'Your password was reset by an administrator.')
    db.session.commit()
    flash(f'Password reset for {user.username}.', 'success')
    return redirect(url_for('user_list'))


@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@role_required('Admin')
def user_delete(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('user_list'))
    name = user.username
    db.session.delete(user)
    log_action('Deleted user account', 'User', user_id, name)
    db.session.commit()
    flash(f'User {name} deleted.', 'info')
    return redirect(url_for('user_list'))


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        f = request.form
        current_pw = f.get('current_password', '')
        new_pw = f.get('new_password', '')
        confirm_pw = f.get('confirm_password', '')
        if not current_user.check_password(current_pw):
            flash('Current password is incorrect.', 'danger')
        elif len(new_pw) < 6:
            flash('New password must be at least 6 characters.', 'danger')
        elif new_pw != confirm_pw:
            flash('New password and confirmation do not match.', 'danger')
        else:
            current_user.set_password(new_pw)
            log_action('Changed own password', 'User', current_user.id, current_user.username)
            db.session.commit()
            flash('Password updated successfully.', 'success')
        return redirect(url_for('settings'))
    return render_template('settings.html')


# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------

@app.route('/notifications')
@login_required
def notification_list():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_on.desc()).limit(50).all()
    return render_template('notifications.html', items=items)


@app.route('/notifications/<int:n_id>/read', methods=['POST'])
@login_required
def notification_read(n_id):
    n = Notification.query.get_or_404(n_id)
    if n.user_id != current_user.id:
        abort(403)
    n.is_read = True
    db.session.commit()
    return redirect(n.link or url_for('notification_list'))


@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def notification_mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return redirect(url_for('notification_list'))


# ---------------------------------------------------------------------------
# AUDIT LOG (Admin / CEO)
# ---------------------------------------------------------------------------

@app.route('/audit-log')
@login_required
@role_required('Admin', 'CEO')
def audit_log_view():
    q = request.args.get('q', '').strip()
    query = AuditLog.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(AuditLog.action.ilike(like), AuditLog.username.ilike(like),
                                     AuditLog.target_repr.ilike(like)))
    logs = query.order_by(AuditLog.timestamp.desc()).limit(300).all()
    return render_template('audit_log.html', logs=logs, q=q)


# ---------------------------------------------------------------------------
# ADMIN (system settings)
# ---------------------------------------------------------------------------

@app.route('/admin')
@login_required
@role_required('Admin')
def admin_home():
    stats = dict(
        users=User.query.count(),
        employees=Employee.query.filter_by(is_archived=False).count(),
        archived_employees=Employee.query.filter_by(is_archived=True).count(),
        departments=Department.query.filter_by(is_archived=False).count(),
        audit_entries=AuditLog.query.count(),
    )
    return render_template('admin.html', stats=stats)


# ---------------------------------------------------------------------------
# REPORTS
# ---------------------------------------------------------------------------

@app.route('/reports')
@login_required
@role_required('Admin', 'CEO', 'HR', 'Manager')
def reports():
    today = date.today()
    start_month = date(today.year, today.month, 1)

    if current_user.role == 'Manager':
        ids = team_employee_ids(current_user.employee_id)
        scope = Employee.query.filter(Employee.id.in_(ids or [-1]))
    else:
        scope = Employee.query.filter_by(is_archived=False)

    scope_ids = [e.id for e in scope.all()]
    dept_counts = db.session.query(Department.name, db.func.count(Employee.id)).\
        outerjoin(Employee, db.and_(Employee.department_id == Department.id, Employee.id.in_(scope_ids or [-1]))).\
        filter(Department.is_archived == False).group_by(Department.id).all()

    leave_by_status = db.session.query(LeaveApplication.status, db.func.count(LeaveApplication.id)).\
        filter(LeaveApplication.employee_id.in_(scope_ids or [-1])).group_by(LeaveApplication.status).all()

    attendance_month = db.session.query(Attendance.status, db.func.count(Attendance.id)).\
        filter(Attendance.employee_id.in_(scope_ids or [-1]), Attendance.att_date >= start_month).\
        group_by(Attendance.status).all()

    payroll_total = db.session.query(db.func.coalesce(db.func.sum(SalarySlip.net_pay), 0)).\
        filter(SalarySlip.employee_id.in_(scope_ids or [-1]), SalarySlip.year == today.year,
               SalarySlip.month == today.month).scalar() if current_user.role in ('Admin', 'CEO', 'HR') else None

    return render_template('reports.html', dept_counts=dept_counts, leave_by_status=leave_by_status,
                            attendance_month=attendance_month, payroll_total=payroll_total, today=today)


# ---------------------------------------------------------------------------
# CHATBOT (Dayflow Assistant) — rule-based HR assistant, scoped to the
# signed-in user's own data and role permissions.
# ---------------------------------------------------------------------------

import re as _re


def _emp_of(user):
    return Employee.query.get(user.employee_id) if user.employee_id else None


def _fmt_money(n):
    return f"₹{n:,.0f}"


def _bot_leave_balance(user):
    emp = _emp_of(user)
    if not emp:
        return "Your login isn't linked to an employee record, so I can't look up leave balances."
    balances = LeaveBalance.query.filter_by(employee_id=emp.id, year=date.today().year).all()
    if not balances:
        return "You don't have any leave balances set up for this year yet. Please check with HR."
    lines = [f"• {b.leave_type.name}: {b.remaining:g} of {b.allocated:g} days remaining" for b in balances]
    return "Here's your leave balance for " + str(date.today().year) + ":\n" + "\n".join(lines)


def _bot_leave_status(user):
    emp = _emp_of(user)
    if not emp:
        return "Your login isn't linked to an employee record, so I can't look up leave requests."
    leaves = LeaveApplication.query.filter_by(employee_id=emp.id).order_by(
        LeaveApplication.applied_on.desc()).limit(5).all()
    if not leaves:
        return "You haven't applied for any leave yet. Head to Leave → Apply for Leave to submit a request."
    lines = [f"• {l.leave_type.name}, {l.from_date} to {l.to_date} — {l.status}" for l in leaves]
    return "Here are your most recent leave requests:\n" + "\n".join(lines)


def _bot_attendance_today(user):
    emp = _emp_of(user)
    if not emp:
        return "Your login isn't linked to an employee record, so I can't check attendance."
    today = date.today()
    att = Attendance.query.filter_by(employee_id=emp.id, att_date=today).first()
    if not att or not att.check_in:
        return "You haven't checked in today yet. Say \"check me in\" and I'll do it for you."
    msg = f"You checked in today at {att.check_in.strftime('%I:%M %p')}"
    if att.check_out:
        msg += f" and checked out at {att.check_out.strftime('%I:%M %p')}."
    else:
        msg += ". You haven't checked out yet."
    return msg


def _bot_do_checkin(user):
    if not user.employee_id:
        return "Your login isn't linked to an employee record, so I can't check you in."
    today = date.today()
    record = Attendance.query.filter_by(employee_id=user.employee_id, att_date=today).first()
    if record and record.check_in:
        return f"You already checked in today at {record.check_in.strftime('%I:%M %p')}."
    if not record:
        record = Attendance(employee_id=user.employee_id, att_date=today, status='Present')
        db.session.add(record)
    record.check_in = datetime.now()
    record.status = 'Present'
    db.session.commit()
    return f"✅ Checked you in at {record.check_in.strftime('%I:%M %p')}. Have a great day!"


def _bot_do_checkout(user):
    if not user.employee_id:
        return "Your login isn't linked to an employee record, so I can't check you out."
    today = date.today()
    record = Attendance.query.filter_by(employee_id=user.employee_id, att_date=today).first()
    if not record or not record.check_in:
        return "You need to check in first before you can check out."
    if record.check_out:
        return f"You already checked out today at {record.check_out.strftime('%I:%M %p')}."
    record.check_out = datetime.now()
    db.session.commit()
    return f"✅ Checked you out at {record.check_out.strftime('%I:%M %p')}. See you next time!"


def _bot_payslip(user):
    emp = _emp_of(user)
    if not emp:
        return "Your login isn't linked to an employee record, so I can't look up payslips."
    slip = SalarySlip.query.filter_by(employee_id=emp.id).order_by(
        SalarySlip.year.desc(), SalarySlip.month.desc()).first()
    if not slip:
        return "No salary slips have been generated for you yet."
    return (f"Your latest payslip is for {slip.month}/{slip.year}: "
            f"gross pay {_fmt_money(slip.gross_pay)}, deductions {_fmt_money(slip.total_deductions)}, "
            f"net pay {_fmt_money(slip.net_pay)}. You can view the full slip under Payroll.")


def _bot_manager(user):
    emp = _emp_of(user)
    if not emp:
        return "Your login isn't linked to an employee record, so I can't look up your manager."
    if not emp.reports_to:
        return "You don't have a reporting manager on file."
    mgr = Employee.query.get(emp.reports_to)
    return f"Your reporting manager is {mgr.full_name} ({mgr.designation})." if mgr else \
        "I couldn't find your manager's record."


def _bot_profile(user):
    emp = _emp_of(user)
    if not emp:
        return "Your login isn't linked to an employee record."
    dept = emp.department.name if emp.department else "no department"
    return (f"You're {emp.full_name}, {emp.designation or 'no designation on file'} in {dept}. "
            f"Employee code {emp.employee_code}, status: {emp.employment_status}, "
            f"joined on {emp.date_of_joining.strftime('%d %b %Y')}.")


def _bot_team_size(user):
    if user.role != 'Manager' or not user.employee_id:
        return "Team lookups are available to managers viewing their own direct reports."
    ids = team_employee_ids(user.employee_id)
    if not ids:
        return "You don't have any direct reports yet."
    names = [e.full_name for e in Employee.query.filter(Employee.id.in_(ids)).all()]
    return f"You have {len(ids)} direct report(s): " + ", ".join(names) + "."


def _bot_pending_approvals(user):
    if user.role == 'Manager' and user.employee_id:
        ids = team_employee_ids(user.employee_id)
        n = LeaveApplication.query.filter(LeaveApplication.employee_id.in_(ids or [-1]),
                                           LeaveApplication.manager_status == 'Pending').count()
        c = AttendanceCorrection.query.filter(AttendanceCorrection.employee_id.in_(ids or [-1]),
                                               AttendanceCorrection.status == 'Pending').count()
        return f"You have {n} leave request(s) and {c} attendance correction(s) awaiting your review."
    if user.role in ('Admin', 'HR'):
        n = LeaveApplication.query.filter_by(hr_status='Pending', approver_stage='hr').count()
        c = AttendanceCorrection.query.filter_by(status='Pending').count()
        return f"There are {n} leave request(s) and {c} attendance correction(s) awaiting HR review."
    if user.role == 'CEO':
        n = LeaveApplication.query.filter(LeaveApplication.hr_status == 'Pending',
                                           LeaveApplication.approver_stage == 'hr').join(
            Employee, LeaveApplication.employee_id == Employee.id).join(
            User, User.employee_id == Employee.id).filter(User.role.in_(['Manager', 'HR'])).count()
        return f"There are {n} escalated leave request(s) awaiting your review."
    return "Pending-approval lookups are available to Managers, HR, Admins, and the CEO."


def _bot_headcount(user):
    if user.role not in ('Admin', 'CEO', 'HR'):
        return "Company-wide headcount is available to Admin, CEO, and HR accounts."
    total = Employee.query.filter_by(is_archived=False).count()
    active = Employee.query.filter_by(is_archived=False, employment_status='Active').count()
    depts = Department.query.filter_by(is_archived=False).count()
    return f"Dayflow currently has {total} employee(s) on record ({active} active) across {depts} department(s)."

def _bot_notifications(user):
    n = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    if n == 0:
        return "You're all caught up — no unread notifications."
    return f"You have {n} unread notification(s). Check the bell icon or the Notifications page for details."


def _bot_help(user):
    lines = [
        "Here's what I can help with:",
        "• \"leave balance\" — your remaining leave days",
        "• \"leave status\" — your recent leave requests",
        "• \"apply for leave\" — how to submit a request",
        "• \"am I checked in\" / \"check me in\" / \"check me out\" — attendance",
        "• \"my payslip\" — your latest salary slip summary",
        "• \"who is my manager\" / \"my profile\" — your details",
        "• \"my notifications\" — unread notification count",
    ]
    if user.role == 'Manager':
        lines.append("• \"my team\" / \"pending approvals\" — your team and pending requests")
    if user.role in ('Admin', 'HR', 'CEO'):
        lines.append("• \"pending approvals\" / \"headcount\" — organization-wide info")
    return "\n".join(lines)


_GREETING_RE = _re.compile(r"\b(hi|hello|hey|good\s?(morning|afternoon|evening))\b", _re.I)
_THANKS_RE = _re.compile(r"\b(thanks|thank you|thx|cheers)\b", _re.I)
_BYE_RE = _re.compile(r"\b(bye|goodbye|see you|later)\b", _re.I)


def generate_bot_reply(user, text):
    """Rule-based intent matching over the user's own HRMS data."""
    t = (text or "").strip().lower()
    if not t:
        return "I didn't catch that — could you type your question?"

    def has(*words):
        return any(_re.search(r"\b" + _re.escape(w) + r"\b", t) for w in words)

    if has("help", "what can you do", "capabilities") or t in ("?", "menu"):
        return _bot_help(user)
    if _GREETING_RE.search(t):
        first = _emp_of(user).first_name if _emp_of(user) else user.username
        return f"Hi {first}! I'm the Dayflow Assistant. Ask me about leave, attendance, payroll, or your profile — or type \"help\" to see everything I can do."
    if _THANKS_RE.search(t):
        return "You're welcome! Let me know if there's anything else I can help with."
    if _BYE_RE.search(t):
        return "Goodbye! Have a great day."

    if has("check me in", "check in now", "clock in", "punch in") or t in ("check in", "checkin"):
        return _bot_do_checkin(user)
    if has("check me out", "check out now", "clock out", "punch out") or t in ("check out", "checkout"):
        return _bot_do_checkout(user)
    if has("checked in", "check-in status", "attendance today", "am i checked in", "did i check in"):
        return _bot_attendance_today(user)

    if has("leave balance", "remaining leave", "leaves left", "how many leave", "leave days"):
        return _bot_leave_balance(user)
    if has("apply for leave", "apply leave", "request leave", "how do i apply", "how to apply"):
        return ("To apply for leave: go to Leave → Apply for Leave, pick a leave type and dates, "
                "add a reason, and submit. Your manager (or HR) will be notified for approval.")
    if has("leave status", "my leave", "pending leave", "leave request"):
        return _bot_leave_status(user)

    if has("payslip", "salary slip", "net pay", "my salary", "how much do i get paid", "pay stub"):
        return _bot_payslip(user)

    if has("who is my manager", "my manager", "reporting manager"):
        return _bot_manager(user)
    if has("my profile", "my designation", "my department", "who am i", "my details"):
        return _bot_profile(user)

    if has("my team", "team size", "direct reports", "who reports to me"):
        return _bot_team_size(user)
    if has("pending approval", "pending approvals", "awaiting approval", "approvals pending"):
        return _bot_pending_approvals(user)
    if has("headcount", "how many employees", "total employees", "total staff"):
        return _bot_headcount(user)
    if has("notification", "notifications", "any updates", "unread"):
        return _bot_notifications(user)

    return ("I'm not sure about that one yet. Try asking about your leave balance, attendance, "
            "payslip, or profile — or type \"help\" to see everything I can do.")


@app.route('/chatbot')
@login_required
def chatbot_page():
    history = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.created_on.asc()).all()
    return render_template('chatbot.html', history=history)


@app.route('/api/chatbot/history')
@login_required
def chatbot_history():
    history = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.created_on.asc()).all()
    return jsonify([
        {'sender': m.sender, 'message': m.message, 'created_on': m.created_on.strftime('%I:%M %p')}
        for m in history
    ])


@app.route('/api/chatbot/send', methods=['POST'])
@login_required
def chatbot_send():
    data = request.get_json(silent=True) or {}
    text = (data.get('message') or '').strip()
    if not text:
        return jsonify({'error': 'Message cannot be empty.'}), 400
    if len(text) > 500:
        text = text[:500]

    user_msg = ChatMessage(user_id=current_user.id, sender='user', message=text)
    db.session.add(user_msg)

    try:
        reply = generate_bot_reply(current_user, text)
    except Exception:
        db.session.rollback()
        reply = "Sorry, something went wrong while processing that. Please try again."

    bot_msg = ChatMessage(user_id=current_user.id, sender='bot', message=reply)
    db.session.add(bot_msg)
    db.session.commit()

    return jsonify({
        'reply': reply,
        'created_on': bot_msg.created_on.strftime('%I:%M %p'),
    })


@app.route('/api/chatbot/clear', methods=['POST'])
@login_required
def chatbot_clear():
    ChatMessage.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# CLI / SEED
# ---------------------------------------------------------------------------

@app.cli.command('seed')
def seed():
    """Seed the database with demo data: flask --app app seed"""
    _seed_data()
    print('Database seeded successfully.')


def _seed_data():
    db.drop_all()
    db.create_all()

    depts = [Department(name=n) for n in ['Engineering', 'Human Resources', 'Sales', 'Marketing', 'Finance']]
    db.session.add_all(depts)
    db.session.commit()

    leave_types = [
        LeaveType(name='Casual Leave', default_days_per_year=12),
        LeaveType(name='Sick Leave', default_days_per_year=10),
        LeaveType(name='Earned Leave', default_days_per_year=15),
    ]
    db.session.add_all(leave_types)
    db.session.commit()

    structure = SalaryStructure(name='Standard', basic_percent=50, hra_percent=20, da_percent=10,
                                 pf_percent=12, professional_tax=200)
    db.session.add(structure)
    db.session.commit()

    def mk_emp(code, first, last, email, designation, dept, gender, salary):
        emp = Employee(employee_code=code, first_name=first, last_name=last, email=email,
                        designation=designation, department_id=dept.id, gender=gender,
                        basic_salary=salary, employment_status='Active',
                        date_of_joining=date.today() - timedelta(days=400))
        db.session.add(emp)
        db.session.commit()
        return emp

    ceo = mk_emp('EMP-0001', 'Meera', 'Iyer', 'meera.iyer@dayflow.com', 'Chief Executive Officer', depts[1], 'Female', 250000)
    hr = mk_emp('EMP-0002', 'Asha', 'Rao', 'asha.rao@dayflow.com', 'HR Manager', depts[1], 'Female', 95000)
    mgr_eng = mk_emp('EMP-0003', 'Karan', 'Singh', 'karan.singh@dayflow.com', 'Engineering Manager', depts[0], 'Male', 140000)
    mgr_sales = mk_emp('EMP-0004', 'Priya', 'Nair', 'priya.nair@dayflow.com', 'Sales Manager', depts[2], 'Female', 120000)
    akash = mk_emp('EMP-0005', 'Akash', 'T', 'akash.t@dayflow.com', 'Software Engineer', depts[0], 'Male', 80000)
    rohan = mk_emp('EMP-0006', 'Rohan', 'Mehta', 'rohan.mehta@dayflow.com', 'Software Engineer', depts[0], 'Male', 78000)
    divya = mk_emp('EMP-0007', 'Divya', 'Kumar', 'divya.kumar@dayflow.com', 'Sales Executive', depts[2], 'Female', 55000)
    sanjay = mk_emp('EMP-0008', 'Sanjay', 'Patel', 'sanjay.patel@dayflow.com', 'Marketing Lead', depts[3], 'Male', 70000)

    hr.reports_to = ceo.id
    mgr_eng.reports_to = ceo.id
    mgr_sales.reports_to = ceo.id
    akash.reports_to = mgr_eng.id
    rohan.reports_to = mgr_eng.id
    divya.reports_to = mgr_sales.id
    sanjay.reports_to = mgr_eng.id
    db.session.commit()

    all_emps = [ceo, hr, mgr_eng, mgr_sales, akash, rohan, divya, sanjay]
    for emp in all_emps:
        for lt in leave_types:
            db.session.add(LeaveBalance(employee_id=emp.id, leave_type_id=lt.id,
                                         year=date.today().year, allocated=lt.default_days_per_year))
    db.session.commit()

    def mk_user(username, email, role, emp, pw):
        u = User(username=username, email=email, role=role, employee_id=emp.id if emp else None)
        u.set_password(pw)
        db.session.add(u)
        return u

    mk_user('admin', 'admin@dayflow.com', 'Admin', None, 'admin123')
    mk_user('meera', ceo.email, 'CEO', ceo, 'ceo12345')
    mk_user('asha', hr.email, 'HR', hr, 'hr123456')
    mk_user('karan', mgr_eng.email, 'Manager', mgr_eng, 'mgr12345')
    mk_user('priya', mgr_sales.email, 'Manager', mgr_sales, 'mgr12345')
    mk_user('akash', akash.email, 'Employee', akash, 'emp123456')
    mk_user('rohan', rohan.email, 'Employee', rohan, 'emp123456')
    mk_user('divya', divya.email, 'Employee', divya, 'emp123456')
    mk_user('sanjay', sanjay.email, 'Employee', sanjay, 'emp123456')
    db.session.commit()

    today = date.today()
    for emp in [akash, rohan, divya, sanjay]:
        for i in range(1, 6):
            d = today - timedelta(days=i)
            if d.weekday() >= 5:
                continue
            db.session.add(Attendance(employee_id=emp.id, att_date=d,
                                       check_in=datetime.combine(d, datetime.strptime('09:10', '%H:%M').time()),
                                       check_out=datetime.combine(d, datetime.strptime('18:05', '%H:%M').time()),
                                       status='Present', is_finalized=True))
    db.session.add(Attendance(employee_id=akash.id, att_date=today,
                               check_in=datetime.combine(today, datetime.strptime('09:12', '%H:%M').time()),
                               status='Present'))
    db.session.commit()

    leave = LeaveApplication(employee_id=rohan.id, leave_type_id=leave_types[0].id,
                              from_date=today + timedelta(days=5), to_date=today + timedelta(days=6),
                              reason='Family function', status='Pending', manager_status='Pending',
                              hr_status='NA', approver_stage='manager')
    db.session.add(leave)
    db.session.commit()

    db.session.add(AuditLog(username='system', role='System', action='Database seeded with demo data'))
    db.session.commit()


with app.app_context():
    db.create_all()
    need_reseed = False
    try:
        User.query.first()
        db.session.execute(db.select(Employee.is_archived)).first()
        db.session.execute(db.select(LeaveApplication.manager_status)).first()
    except Exception:
        need_reseed = True
    if need_reseed or not User.query.first():
        db.drop_all()
        db.create_all()
        _seed_data()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
