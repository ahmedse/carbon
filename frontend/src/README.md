# src

This folder contains the source code for the frontend React application.

---

## 📁 Structure

```
src/
├── App.jsx                 # Root component: theme, authentication, routing
├── main.jsx                # Entry point: renders <App /> to the DOM
├── Router.jsx              # Application routes and route protection
├── index.css               # Global styles (fonts, colors, resets)
├── App.css                 # App and logo-specific styles
├── context/                # (If present) React context providers (e.g. Auth)
├── layouts/                # (If present) Layout components (wrappers, shells)
├── pages/                  # Route-level React components (see below)
├── styles/                 # (If present) Theme or utility style files
└── ...                     # Other feature-specific folders or files
```

---

## ⚙️ Main Files

- **App.jsx**  
  Sets up the global theme (light/dark/system), authentication context, and application routing.
- **main.jsx**  
  The entry point. Mounts the React app inside the `#root` DOM element.
- **Router.jsx**  
  Defines all major application routes. Handles authentication and role-based route protection.
- **index.css & App.css**  
  Global and application-level CSS styles.

---

## 🗂️ Key Folders

- **context/**  
  Holds React Context Providers (e.g., for authentication, theme, settings).
- **layouts/**  
  Layout components for wrapping pages (e.g., MainLayout).
- **pages/**  
  All page-level components (Login, Dashboard, AdminDashboard, etc).  
  See [`pages/README.md`](./pages/README.md) for more.
- **styles/**  
  (Optional) Custom MUI themes, design tokens, or shared style modules.

---

## 📝 Notes

- All application logic, UI, and routing starts from this folder.
- For static assets (images, logos), use the `public/` directory at the frontend root.

---

**See [`pages/README.md`](./pages/README.md) for documentation on the app's page-level routes and structure.**
