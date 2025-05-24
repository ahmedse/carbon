// File: frontend/src/main.jsx
// Purpose: Application entry point; renders the root App component to the DOM.
// Location: frontend/src/

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Mount the root React component to the DOM
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)