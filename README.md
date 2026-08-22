# Dayflow HRMS

A production-style **Human Resource Management System** built with Flask +
SQLAlchemy + SQLite, featuring real organizational hierarchy, role-based
access control, reversible lifecycle workflows, multi-stage approvals,
notifications, and a full audit trail.

## Roles & hierarchy

`Admin → CEO → HR → Manager → Employee`

| Role | Scope |
|---|---|
| **Admin** | Full system access: user accounts, departments, leave types, audit log, system settings |
| **CEO** | Organization-wide read access, approves requests escalated to the HR stage from Managers/HR |
| **HR** | Manages employees, departments, attendance, leave approvals, payroll, recruitment |
| **Manager** | Manages their direct-report team: attendance, leave approvals for their team |
| **Employee** | Self-service: attendance, leave applications, payslips, profile, notifications |

Every route enforces this in the backend (`@role_required(...)` / per-record
ownership checks) — permissions are never just hidden buttons.

## Reversible lifecycles

- **Employee**: Onboarding → Active → On Leave/Notice Period → Inactive/Exited, plus **Archive → Restore**, with permanent delete only allowed once archived.
- **Leave**: Pending → Manager (if applicable) → HR → Approved/Rejected, with **Withdraw** (while pending) and **Cancel** (after approval, before start date). Balances and attendance are corrected automatically on cancel.
- **Attendance**: Employees can't edit finalized records directly — they submit a **Correction Request** that a Manager/HR approves or rejects.
- **Departments / Leave Types / Job Openings**: Archive/restore instead of hard delete; hard delete blocked while in use.
- **User accounts**: Activate/deactivate, change role, reset password, delete — all logged.

## Notifications & audit log

Every approval, rejection, status change, and administrative action writes to
the `AuditLog` table (who / what / when / old → new value) and, where
relevant, creates a `Notification` for the affected user. Both are visible
in-app under **Notifications** and **Audit Log** (Admin/CEO).

## Dayflow Assistant (chatbot)

Every signed-in page has a floating "Assistant" bubble (bottom-right) plus a full
**Assistant** page in the sidebar. It's a rule-based HR assistant that answers
using your own live data — no external API key required, works fully offline:

- Leave balance / leave status / how to apply for leave
- Attendance: "am I checked in", and it can actually check you in/out on request
- Latest payslip summary
- Your manager, designation, department, and profile details
- Unread notification count
- Managers: team size and pending team approvals
- Admin / HR / CEO: headcount and pending org-wide approvals

Conversations persist per-user in the database and can be cleared from the
Assistant page.

## Tech stack

- **Backend:** Python 3, Flask, Flask-SQLAlchemy, Flask-Login
- **Database:** SQLite (swap `SQLALCHEMY_DATABASE_URI` for Postgres/MySQL in production)
- **Frontend:** Server-rendered Jinja2 templates, Bootstrap 5, Font Awesome, custom "Dayflow" design system (`static/css/style.css`)

## Getting started

```bash
# 1. Create a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run (the database is auto-created and seeded with demo data on first run)
python app.py
# -> http://localhost:5000
```

## Demo accounts

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Admin |
| `meera` | `ceo12345` | CEO |
| `asha` | `hr123456` | HR |
| `karan` | `mgr12345` | Manager (Engineering) |
| `priya` | `mgr12345` | Manager (Sales) |
| `akash` | `emp123456` | Employee |
| `rohan` | `emp123456` | Employee |
| `divya` | `emp123456` | Employee |
| `sanjay` | `emp123456` | Employee |

To reset and reseed the database at any time:

```bash
rm instance/hrms.db
python app.py
```
