# components

This folder contains all shared UI components for the admin dashboard.

---

## 📁 Structure

```
components/
├── Sidebar.jsx            # Responsive, collapsible sidebar navigation
├── SidebarHeader.jsx      # Sidebar header with project/cycle info
├── SidebarMenu.jsx        # Renders sidebar menu and sub-menus
├── menuConfig.js          # Sidebar menu configuration (labels, icons, submenus)
├── ChartCard.jsx          # Card for displaying line or pie charts (uses recharts)
├── StatCard.jsx           # Card for displaying a single statistic
├── Topbar.jsx             # Top navigation bar with dashboard title and sidebar toggle
└── ...                    # Add more admin widgets/components as needed
```

---

## 🏗️ Main Components

- **Sidebar.jsx**  
  Collapsible and pinnable navigation sidebar for the admin dashboard. Includes menu and project/cycle info.
- **SidebarHeader.jsx**  
  Displays the current project and cycle at the top of the sidebar.
- **SidebarMenu.jsx**  
  Renders the main sidebar menu and handles nested sub-menus. Uses the configuration in `menuConfig.js`.
- **menuConfig.js**  
  JavaScript object defining sidebar menu structure, labels, icons, and sub-menu items.
- **ChartCard.jsx**  
  Card component for rendering charts (`line` and `pie`) with [recharts](https://recharts.org/).
- **StatCard.jsx**  
  Card for displaying a single statistic (value, label, unit).
- **Topbar.jsx**  
  AppBar for the top of the dashboard, includes dashboard title and sidebar toggle for mobile.

---

## 📝 Usage

- These components are imported and composed in `AdminDashboard.jsx` and related dashboard/module files.
- They help maintain a **consistent, responsive admin dashboard UI**.
- You can extend the sidebar menu by editing `menuConfig.js`.

---

**For more details on how these components are used, see [`../AdminDashboard.jsx`](../AdminDashboard.jsx).**
