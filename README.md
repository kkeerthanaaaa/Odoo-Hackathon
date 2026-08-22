# 🌊 Dayflow HRMS

> **Every workday, perfectly aligned.**

A production-style **Human Resource Management System (HRMS)** built with **Flask, SQLAlchemy, SQLite, Jinja2, and Bootstrap 5**.

Dayflow provides a complete HR workflow with **role-based access control, organizational hierarchy, employee lifecycle management, multi-stage leave approvals, attendance corrections, notifications, audit trails, payroll visibility, and an offline AI-style HR Assistant.**

---

## 📸 Screenshots


### 🔐 Login


<img width="1600" height="792" alt="544835c6-af3e-4474-8f3d-d0c76be50199" src="https://github.com/user-attachments/assets/0d7977eb-8cfc-487c-9e8e-5b475888af8c" />


### 👤 Employee Dashboard


<img width="1600" height="773" alt="4b5b4f45-7593-4d1e-9021-983968f368c4" src="https://github.com/user-attachments/assets/cb4e127d-b0be-4acf-8abc-46fd353fdfdc" />


### 🧑‍💼 Manager Dashboard


<img width="1600" height="760" alt="0f3a0b13-0ea7-4ada-821b-84030b89d4d7" src="https://github.com/user-attachments/assets/fd47cd2c-eabb-4c18-86b3-1956297d079d" />


### 🏢 HR Dashboard


<img width="1600" height="764" alt="651dd653-b5ce-478a-90d3-5e821c358218" src="https://github.com/user-attachments/assets/775c3406-7e7c-4135-a084-f3d914f39d2d" />


### 👑 CEO Dashboard


<img width="1600" height="764" alt="62eae4c8-353f-4f92-8020-a5f772350e38" src="https://github.com/user-attachments/assets/002df74b-9ee9-4d1e-9be7-778cfe78bd9d" />


### ⚙️ Admin Dashboard


<img width="1600" height="771" alt="b6575bbc-0b5f-4b45-ad01-5433f60c6f0c" src="https://github.com/user-attachments/assets/81dda456-9eb9-4382-bd26-1c3720633b7d" />


---


# ✨ Features

## 🔐 Authentication & Authorization

* Secure login and logout
* Role-based access control
* Backend-enforced permissions
* Per-record ownership validation
* Password reset functionality
* User activation/deactivation
* Role management

### Role Hierarchy

```text
Admin
  ↓
CEO
  ↓
HR
  ↓
Manager
  ↓
Employee
```

---

# 👥 Role-Based Dashboards

| Role              | Capabilities                                       |
| ----------------- | -------------------------------------------------- |
| 👑 **Admin**      | Full system administration                         |
| 🏢 **CEO**        | Organization-wide visibility and approvals         |
| 🧑‍💼 **HR**      | Employees, attendance, payroll, recruitment, leave |
| 👨‍💼 **Manager** | Direct-report team management                      |
| 👤 **Employee**   | Attendance, leave, profile, payslips               |

Each role receives a different dashboard and only has access to authorized resources.

---

# 👤 Employee Management

Complete employee lifecycle management:

```text
Onboarding
    ↓
Active
    ↓
On Leave / Notice Period
    ↓
Inactive / Exited
```

Additional capabilities:

* Employee profiles
* Department assignment
* Designation
* Manager assignment
* Employee status
* Joining information
* Archive employee
* Restore employee
* Permanent deletion only after archival

---

# 🏖️ Leave Management

<img width="1600" height="753" alt="7c865ca1-3c5c-4ea6-8182-2150b895fb44" src="https://github.com/user-attachments/assets/cb7d25f9-67e4-4ea6-bbb3-b55b8240cee9" />


Multi-stage leave approval workflow:

```text
Employee
    ↓
Manager
    ↓
HR
    ↓
Approved / Rejected
```

Features include:

* Apply for leave
* View leave balance
* Manager approval
* HR approval
* Leave rejection
* Leave withdrawal
* Leave cancellation
* Automatic balance correction
* Attendance correction after cancellation
* Leave history

---

# 🕒 Attendance Management

Employees can:

* Check in
* Check out
* View attendance history
* View daily attendance status

Finalized attendance records cannot be directly modified.

Instead:

```text
Employee
    ↓
Correction Request
    ↓
Manager / HR
    ↓
Approve / Reject
```

This maintains a reliable attendance history.

---

# 💰 Payroll

<img width="1600" height="757" alt="image" src="https://github.com/user-attachments/assets/1067b12d-505c-4e24-9f62-dd58052aea84" />


HR can manage payroll information while employees can securely access their own payslips.

Employees can:

* View salary information
* View latest payslip
* Review payroll history

The Dayflow Assistant can also provide a quick summary of the latest payslip.

---

# 🔔 Notifications

Dayflow automatically generates notifications for important events.

Examples:

* Leave approved
* Leave rejected
* Leave cancelled
* Attendance correction approved
* Attendance correction rejected
* Employee status changes
* Administrative actions
* Approval requests

Users can view their notifications directly from the application.

---

# 📋 Audit Trail

Every important administrative or workflow action is recorded in the `AuditLog`.

The audit system records:

```text
Who
↓
What action
↓
When
↓
Old value
↓
New value
```

Administrators and CEOs can review the audit history.

This provides accountability and traceability across the system.

---

# 🔄 Reversible Workflows

Dayflow avoids unnecessary permanent deletion.

### Employee

```text
Active → Notice Period → Inactive
                  ↓
               Archive
                  ↓
               Restore
```

### Departments

```text
Active → Archived
           ↓
         Restore
```

### Leave Types

```text
Active → Archived
           ↓
         Restore
```

### Job Openings

```text
Active → Archived
           ↓
         Restore
```

Hard deletion is blocked when records are still being used by other parts of the system.

---

# 🤖 Dayflow Assistant

Dayflow includes a built-in **rule-based HR Assistant** that works using the application's own live database.

### No external API required

The assistant works **fully offline** and does not require an external LLM API key.

It can answer questions such as:

```text
"What is my leave balance?"

"Am I checked in?"

"Who is my manager?"

"What is my department?"

"What is my designation?"

"Show my latest payslip."

"How do I apply for leave?"

"How many unread notifications do I have?"
```

Managers can also ask about:

```text
Team size
Pending team approvals
```

HR / CEO / Admin users can access:

```text
Organization headcount
Pending organization-wide approvals
```

The assistant can also perform supported actions such as checking an employee in/out.

### Assistant UI

![Dayflow Assistant](screenshots/assistant.png)

Conversations are persisted per user and can be cleared from the Assistant page.

---

# 🔔 Notifications + Audit Architecture

```text
User Action
     │
     ▼
Backend Validation
     │
     ▼
Database Update
     │
     ├──────────────► AuditLog
     │
     └──────────────► Notification
                           │
                           ▼
                      Affected User
```

---

# 🏗️ Application Architecture

```text
┌───────────────────────────────────┐
│            Browser                │
│     Jinja2 + Bootstrap 5          │
└────────────────┬──────────────────┘
                 │
                 ▼
┌───────────────────────────────────┐
│          Flask Application        │
│                                   │
│ Authentication                    │
│ Role-Based Authorization          │
│ Business Logic                    │
│ HR Workflows                      │
│ Notifications                     │
│ Audit Logging                     │
│ Dayflow Assistant                 │
└────────────────┬──────────────────┘
                 │
                 ▼
┌───────────────────────────────────┐
│        Flask-SQLAlchemy           │
└────────────────┬──────────────────┘
                 │
                 ▼
┌───────────────────────────────────┐
│             SQLite                │
└───────────────────────────────────┘
```

---

# 🛠️ Tech Stack

### Backend

* Python 3
* Flask
* Flask-SQLAlchemy
* Flask-Login

### Database

* SQLite
* SQLAlchemy ORM

> SQLite can be replaced with PostgreSQL or MySQL by changing the database configuration.

### Frontend

* HTML5
* Jinja2
* Bootstrap 5
* CSS3
* Font Awesome
* Custom Dayflow Design System

---

# 📂 Project Structure

```text
Dayflow/
│
├── app.py
├── requirements.txt
├── README.md
│
├── instance/
│   └── hrms.db
│
├── templates/
│   ├── auth/
│   ├── admin/
│   ├── ceo/
│   ├── hr/
│   ├── manager/
│   ├── employee/
│   └── assistant/
│
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   └── images/
│
└── screenshots/
    ├── login.png
    ├── employee-dashboard.png
    ├── manager-dashboard.png
    ├── hr-dashboard.png
    ├── ceo-dashboard.png
    ├── admin-dashboard.png
    └── assistant.png
```

---

# 🚀 Getting Started

## 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd Dayflow
```

## 2. Create a virtual environment

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Run the application

```bash
python app.py
```

Open:

```text
http://localhost:5000
```

The database is automatically created and seeded with demo data on the first run.

---

# 👨‍💻 Demo Accounts

| Username | Password    | Role     |
| -------- | ----------- | -------- |
| `admin`  | `admin123`  | Admin    |
| `meera`  | `ceo12345`  | CEO      |
| `asha`   | `hr123456`  | HR       |
| `karan`  | `mgr12345`  | Manager  |
| `priya`  | `mgr12345`  | Manager  |
| `akash`  | `emp123456` | Employee |
| `rohan`  | `emp123456` | Employee |
| `divya`  | `emp123456` | Employee |
| `sanjay` | `emp123456` | Employee |

> ⚠️ These credentials are intended for local/demo usage only. Change all passwords before deploying to production.

---

# 🗄️ Reset Database

To remove the existing database and recreate the demo data:

### Windows

```powershell
Remove-Item instance\hrms.db
python app.py
```

### Linux / macOS

```bash
rm instance/hrms.db
python app.py
```

---

# 🔒 Security

Dayflow enforces authorization on the **backend**, not only through frontend visibility.

Important security mechanisms include:

* Role-based authorization
* Record ownership validation
* Password authentication
* Account activation/deactivation
* Protected routes
* Audit logging
* Controlled administrative actions
* Restricted permanent deletion

> UI buttons being hidden does **not** constitute authorization. Every protected operation is validated server-side.

---

# 📊 Core Modules

```text
Authentication
      │
      ├── User Management
      ├── Employee Management
      ├── Department Management
      ├── Attendance
      ├── Leave Management
      ├── Payroll
      ├── Recruitment
      ├── Notifications
      ├── Audit Log
      ├── Profile Management
      └── Dayflow Assistant
```

---

# 🌟 Why Dayflow?

Dayflow is designed around the idea that an HRMS should be more than a collection of CRUD pages.

It provides:

* ✅ Real organizational hierarchy
* ✅ Role-based access control
* ✅ Multi-stage approvals
* ✅ Reversible workflows
* ✅ Attendance correction workflows
* ✅ Automated notifications
* ✅ Complete audit history
* ✅ Employee self-service
* ✅ Payroll visibility
* ✅ Offline HR Assistant
* ✅ Persistent conversations
* ✅ Production-oriented backend authorization

---

# 🔮 Future Enhancements

Potential future improvements include:

* PostgreSQL production deployment
* Docker support
* Email notifications
* Real-time notifications
* Advanced analytics
* Employee performance management
* Recruitment pipeline enhancements
* Mobile-responsive improvements
* LLM-powered HR Assistant
* Cloud deployment
* Automated payroll processing

---

# 👨‍💻 Development

Built as a production-style HRMS project demonstrating:

**Flask + SQLAlchemy + RBAC + Workflow Management + Audit Logging + Notifications + Employee Self-Service**

---

## 📜 License

This project is available for educational and development purposes.

---

# ⭐ Support

If you find **Dayflow HRMS** useful, consider giving the repository a ⭐ on GitHub.
