# AdminDashboard

This folder contains the components and modules for the administrator dashboard.

---

## 📁 Structure

```
AdminDashboard/
├── AdminDashboard.jsx         # Main admin dashboard layout and internal router
├── DashboardHome.jsx          # Home page for admin dashboard (stats, charts)
├── WaterModule.jsx            # Water-specific admin module (if present)
├── ElectricityModule.jsx      # Electricity-specific admin module (if present)
├── GasModule.jsx              # Gas-specific admin module (if present)
├── components/                # Shared components for admin dashboard (see below)
└── ...                        # Add more admin modules as needed
```

---

## 🏗️ Main Files

- **AdminDashboard.jsx**  
  Main entry point for the admin dashboard, sets up layout (sidebar, topbar), and defines internal routes for admin modules.
- **DashboardHome.jsx**  
  The default landing page for admins, showing stats and charts for the selected context (project, cycle, or module).
- **WaterModule.jsx**, **ElectricityModule.jsx**, **GasModule.jsx**  
  (If present) Each file implements a dashboard view for a specific resource domain in the project.
- **components/**  
  Shared UI components for the admin dashboard (sidebar, menu, cards, etc.).  
  See [`components/README.md`](./components/README.md).

---

## 📝 Notes

- The admin dashboard is **context-aware**; it adapts its title and contents based on the selected project/cycle/module.
- Sidebar navigation and internal routing are handled by `AdminDashboard.jsx`.
- All admin dashboard widgets and menu logic are shared via the `components/` subfolder.

---

**See [`components/README.md`](./components/README.md) for documentation on shared admin dashboard widgets.**
