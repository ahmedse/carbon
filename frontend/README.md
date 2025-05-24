
# Frontend

This directory contains the React-based frontend for the AAST Carbon Platform.

---

## 📁 Structure

```
frontend/
├── public/                # Static assets (e.g., favicon, logo images)
├── src/                   # Source code (all app logic and pages)
├── Dockerfile             # Docker config for frontend (rename if needed)
├── package.json           # NPM package manifest
├── ...                    # Other config files
```

---

## 🚀 Getting Started

### 1. Install dependencies

```bash
npm install
```

### 2. Run locally

```bash
npm run dev
```
App runs by default at [http://localhost:5173](http://localhost:5173).

### 3. Build for production

```bash
npm run build
```

### 4. Run in Docker

```bash
docker build -t my-frontend .
docker run -p 5173:5173 my-frontend
```

---

## 🌟 Features

- **Role-based route protection**
- **Responsive layout**
- **Theme switching (light/dark/system)**
- **Material UI for consistent design**
- **JWT authentication**

---

## 📚 Further Structure

- See [`src/README.md`](./src/README.md) for details on the source code.
- See [`Dockerfile`](./Dockerfile) for container usage.

---

## 📝 License

This project is intended for internal use at AAST Carbon Platform. For license or reuse, please contact the project owners.