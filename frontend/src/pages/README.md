# pages

This folder contains all route-level (page) React components for the frontend app.

---

## 📁 Structure

```
pages/
├── Login.jsx                     # Login screen (authentication)
├── Dashboard.jsx                 # Main dashboard (context selection, routing)
├── AdminDashboard/               # Admin dashboard and modules (see below)
├── AuditorDashboard.jsx          # Auditor's role dashboard
├── DataOwnerDashboard.jsx        # Data owner's role dashboard
└── ...                           # Add more pages as needed
```

---

## 🗺️ Main Pages

- **Login.jsx**  
  Handles user authentication and login form.
- **Dashboard.jsx**  
  Entry point after login. Lets user select a context (project, cycle, module) and loads the appropriate dashboard based on their assigned roles.
- **AdminDashboard/**  
  Contains the full admin dashboard with its own modules, sidebar, and internal routing.  
  See [`AdminDashboard/README.md`](./AdminDashboard/README.md) for details.
- **AuditorDashboard.jsx**  
  Dashboard for users with the "auditor" role.
- **DataOwnerDashboard.jsx**  
  Dashboard for users with the "data_owner" role.

---

## 📝 Notes

- Routing and role-based protection are handled by the global `Router.jsx` (in `src/`).
- Each dashboard (Admin, Auditor, Data Owner) is modular and context-aware.
- Add new pages here for new app-level sections or roles.

---

**See [`AdminDashboard/README.md`](./AdminDashboard/README.md) for more on the administrator dashboard's structure.**

