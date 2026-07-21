# Carbon UI Polish & Pulse Integration Plan

**Reference Platform**: Gigacast (clearturn.ai power forecasting platform)  
**Target Platform**: Carbon Data Trust Platform  
**Goal**: Modernize Carbon UI to match Gigacast's polish, add Pulse AI widget integration  
**Design Language**: Zinc/blue palette, compact spacing, IDE-inspired shell layout

---

## 1. Executive Summary

Transform Carbon's UI from basic Material-UI layout to a polished, production-grade IDE-inspired interface matching Gigacast's design standards. Key improvements include:

- **Header Redesign**: Compact 35px branded header with refined user menu
- **Footer Enhancement**: Minimal, professional footer with proper branding
- **Shell Architecture**: VSCode-inspired layout with Activity Bar, resizable sidebar, status bar
- **Pulse Widget**: Floating button + resizable copilot pane for AI assistance
- **Design System**: Unified zinc/blue theme with light/dark mode support
- **Enhanced Navigation**: Studio-based navigation with keyboard shortcuts

---

## 2. Current State Analysis

### 2.1 Carbon UI Current Architecture

**Layout Structure:**
```
├── App.jsx (React Router)
├── Layout.jsx (Header + Sidebar + Content + Footer)
├── Header.jsx (56px AppBar with logo, user menu)
├── Sidebar.jsx (Collapsible nav menu)
├── Footer.jsx (Minimal copyright text)
└── Pages (Dashboard, Data Entry, Admin)
```

**Theme:**
- Material-UI default with custom zinc/blue palette
- Basic light/dark mode support via `carbonTheme.js`
- Standard MUI components with minimal customization

**Issues:**
- ❌ Large, space-wasting header (56px vs Gigacast's 35px)
- ❌ Basic user menu without role badges or profile details
- ❌ No status bar for system state/shortcuts
- ❌ Fixed sidebar (not resizable)
- ❌ No AI copilot integration
- ❌ No keyboard shortcuts (Ctrl+B, Ctrl+K, etc.)
- ❌ No activity bar for quick studio switching
- ❌ Standard footer lacks professional touch

### 2.2 Gigacast UI Reference Architecture

**Shell Layout:**
```
┌─────────────────────────────────────────────┐
│ Header (35px, branded, gradient overlay)   │
├──┬────────────────────────────────┬─────────┤
│A │ Sidebar         │ Editor Area  │Copilot  │
│c │ (resizable)     │              │(optional)│
│t │                 │              │         │
│i │                 ├──────────────┤         │
│v │                 │ Panel (opt)  │         │
│i │                 │              │         │
│t │                 │              │         │
│y │                 │              │         │
│  │                 │              │         │
│B │                 │              │         │
│a │                 │              │         │
│r │                 │              │         │
├──┴────────────────────────────────┴─────────┤
│ Status Bar (22px, system state + toggles)   │
└─────────────────────────────────────────────┘
```

**Key Features:**
- ✅ Compact 35px header with gradient overlay
- ✅ 48px activity bar for studio switching
- ✅ Resizable sidebar (250-360px range)
- ✅ Resizable copilot pane (300-600px)
- ✅ Status bar with system state + toggle buttons
- ✅ Command palette (Ctrl+K)
- ✅ Keyboard shortcuts (Ctrl+B, Ctrl+J, Ctrl+\\)
- ✅ Theme toggle in header
- ✅ Professional user menu with role badges

---

## 3. Design System Alignment

### 3.1 Color Palette (Already Aligned ✅)

Both platforms use identical zinc/blue palette:

```javascript
// Primary colors (shared)
primary: { main: '#2563eb', light: '#3b82f6', dark: '#1d4ed8' }
secondary: { main: '#475569', light: '#64748b', dark: '#334155' }

// Light theme backgrounds
background: { default: '#ffffff', paper: '#fafafa', dark: '#f4f4f5' }
text: { primary: '#18181b', secondary: '#71717a', disabled: '#a1a1aa' }

// Dark theme backgrounds
background: { default: '#09090b', paper: '#18181b', dark: '#27272a' }
text: { primary: '#f4f4f5', secondary: '#a1a1aa', disabled: '#71717a' }
```

**Action Required:** None - Carbon already inherits Gigacast theme ✅

### 3.2 Typography (Already Aligned ✅)

Both use Inter font with identical sizing:
- Font: "Inter", system-ui, sans-serif
- Base size: 14px
- Headings: 600-700 weight, -0.02em to -0.01em letter spacing
- Body: 0.875rem (14px), 1.5 line height

**Action Required:** None - Carbon already uses correct typography ✅

### 3.3 Spacing & Borders

**Carbon Current:** Standard MUI spacing (8px base), heavy shadows  
**Gigacast Standard:** 8px base, subtle borders over shadows

**Action Required:**
- ✅ Already using 8px spacing base
- ⚠️ Update component overrides to prefer borders over shadows
- ⚠️ Add compact padding standards (px: 1.25, py: 0.375 for small buttons)

---

## 4. Component-by-Component Redesign

### 4.1 Header Component

**Current State:**
```jsx
// carbon-frontend/src/components/Header.jsx
<AppBar position="sticky" sx={{ bgcolor: "#fff", minHeight: 56 }}>
  <Toolbar sx={{ px: 2 }}>
    <img src={logo} /> 
    <Typography>AASTMT Carbon Platform</Typography>
    <Box flexGrow={1} />
    <IconButton><HelpOutline /></IconButton>
    <IconButton><Notifications /></IconButton>
    <IconButton><Settings /></IconButton>
    <Avatar onClick={handleMenu}>{initials}</Avatar>
  </Toolbar>
</AppBar>
```

**Target State (Gigacast-inspired):**
```jsx
<Box component="header" sx={{
  height: 35, minHeight: 35,
  bgcolor: 'background.paper',
  borderBottom: '1px solid', borderColor: 'divider',
  px: 1.25, gap: 1,
  '&::after': {
    // Gradient overlay (light: blue fade, dark: zinc fade)
    background: (t) => t.palette.mode === 'light'
      ? 'linear-gradient(90deg, rgba(14,165,233,0.08) 0%, transparent 55%)'
      : 'linear-gradient(90deg, rgba(56,189,248,0.12) 0%, transparent 55%)'
  }
}}>
  {/* Brand pill */}
  <Box sx={{ px: 0.75, py: 0.375, borderRadius: 1.25, border: '1px solid', 
    borderColor: 'divider', bgcolor: 'rgba(255,255,255,0.82)' }}>
    <img src={logo} style={{ width: 14, height: 14 }} />
    <Typography sx={{ fontSize: '0.75rem', fontWeight: 700 }}>Carbon</Typography>
  </Box>
  
  <Box flex={1} />
  
  {/* Compact action bar */}
  <Box sx={{ px: 0.5, py: 0.375, borderRadius: 999, border: '1px solid', 
    borderColor: 'divider' }}>
    <Tooltip title="Dark mode"><IconButton size="small" /></Tooltip>
    <Divider orientation="vertical" />
    <Tooltip title={user?.username}>
      <Avatar sx={{ width: 26, height: 26 }} onClick={handleMenu} />
    </Tooltip>
  </Box>
</Box>
```

**Key Changes:**
- ✅ Height: 56px → 35px (saves 21px vertical space)
- ✅ Gradient overlay background (brand identity)
- ✅ Branded logo pill with border + shadow
- ✅ Compact icon buttons (26px vs 40px)
- ✅ Rounded action bar container
- ✅ Theme toggle moved to header

**User Menu Popover:**
```jsx
<Popover sx={{ width: 220, borderRadius: 1.5 }}>
  {/* Identity block */}
  <Box sx={{ px: 1.5, pt: 1.25, pb: 1 }}>
    <Box sx={{ display: 'flex', gap: 1 }}>
      <Avatar sx={{ width: 30, height: 30 }}>{initials}</Avatar>
      <Box>
        <Typography sx={{ fontSize: '0.75rem', fontWeight: 600 }}>
          {user?.username}
        </Typography>
        <Typography sx={{ fontSize: '0.5625rem', color: 'text.disabled' }}>
          {user?.email}
        </Typography>
      </Box>
    </Box>
    <RoleBadge role={primaryRole} /> {/* NEW: admin/steward/auditor badge */}
  </Box>
  
  <Divider sx={{ my: 0.5 }} />
  
  {/* Menu items */}
  <MenuRow icon={SettingsOutlined} label="Account Settings" />
  <MenuRow icon={KeyboardOutlined} label="Keyboard Shortcuts" />
  
  <Divider sx={{ my: 0.5 }} />
  
  <MenuRow icon={LogoutOutlined} label="Sign out" danger />
</Popover>
```

**New Components:**
- `RoleBadge`: Colored pill showing admin/org_steward/auditor role
- `MenuRow`: Reusable menu item with icon + hover state

### 4.2 Footer Component

**Current State:**
```jsx
<Box sx={{ py: 2, textAlign: "center" }}>
  <Typography variant="body2" color="text.secondary">
    © 2026 AASTMT Carbon Platform. All rights reserved.
  </Typography>
</Box>
```

**Target State (Gigacast-inspired):**
```jsx
<Box sx={{ 
  py: 1.5, px: 2, 
  bgcolor: 'background.paper', 
  borderTop: '1px solid', 
  borderColor: 'divider',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center'
}}>
  <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary' }}>
    © {new Date().getFullYear()} AASTMT Carbon Data Trust Platform
  </Typography>
  <Box sx={{ display: 'flex', gap: 2 }}>
    <Link sx={{ fontSize: '0.6875rem' }}>Privacy</Link>
    <Link sx={{ fontSize: '0.6875rem' }}>Terms</Link>
    <Link sx={{ fontSize: '0.6875rem' }}>Support</Link>
  </Box>
</Box>
```

**Key Changes:**
- ✅ Add border-top separator
- ✅ Flex layout with left/right content
- ✅ Add Privacy/Terms/Support links
- ✅ Smaller font (11px vs 13px)
- ✅ Background color for visual separation

### 4.3 Shell Architecture (NEW)

**Create New Component:** `carbon-frontend/src/shell/Shell.jsx`

Implements VSCode-inspired IDE layout:

```jsx
<Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
  {/* Header */}
  <Header />
  
  {/* Main Content */}
  <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
    {/* Activity Bar (48px) */}
    <ActivityBar 
      studios={studios} 
      activeStudio={activeStudio} 
      onStudioChange={handleStudioChange} 
    />
    
    {/* Resizable Sidebar */}
    <Drawer 
      variant="persistent" 
      open={sidebarVisible}
      sx={{ width: drawerWidth }} // 250-360px range
    >
      <Box sx={{ position: 'absolute', right: 0, width: 6, cursor: 'col-resize' }} 
        onMouseDown={handleResize} 
      />
      <ShellSidebar activeStudio={activeStudio} onNavigate={handleNavigate} />
    </Drawer>
    
    {/* Resizable Main + Copilot Panes (using Allotment) */}
    <Allotment onChange={handlePaneResize}>
      <Allotment.Pane>
        {/* Editor Area (main content - Outlet for React Router) */}
        <EditorArea />
      </Allotment.Pane>
      
      {copilotVisible && (
        <Allotment.Pane minSize={300} preferredSize={400} maxSize={600}>
          <CopilotPane onClose={toggleCopilot} />
        </Allotment.Pane>
      )}
    </Allotment>
  </Box>
  
  {/* Status Bar */}
  <StatusBar 
    sidebarVisible={sidebarVisible}
    copilotVisible={copilotVisible}
    onToggleSidebar={toggleSidebar}
    onToggleCopilot={toggleCopilot}
  />
  
  {/* Command Palette (Ctrl+K) */}
  <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
</Box>
```

**Key Features:**
- ✅ 100vh full-screen layout (no scrolling chrome)
- ✅ Resizable sidebar with drag handle
- ✅ Resizable copilot pane (Allotment library)
- ✅ Persistent layout state in localStorage
- ✅ Keyboard shortcuts (Ctrl+B, Ctrl+K, Ctrl+\\)

### 4.4 Activity Bar (NEW)

**Create:** `carbon-frontend/src/shell/ActivityBar.jsx`

```jsx
<Box sx={{ 
  width: 48, 
  bgcolor: 'background.dark', 
  borderRight: '1px solid', 
  borderColor: 'divider',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  py: 1
}}>
  {/* Main studios */}
  {studios.filter(s => !s.bottom).map(studio => (
    <Tooltip title={studio.label} placement="right" key={studio.id}>
      <IconButton 
        size="small"
        onClick={() => onStudioChange(studio.id)}
        sx={{
          width: 40, height: 40, borderRadius: 1,
          color: activeStudio === studio.id ? 'primary.main' : 'text.secondary',
          bgcolor: activeStudio === studio.id ? 'action.selected' : 'transparent',
          '&:hover': { bgcolor: 'action.hover' }
        }}
      >
        {studio.icon}
      </IconButton>
    </Tooltip>
  ))}
  
  <Box sx={{ flex: 1 }} />
  
  {/* Bottom studios (Settings, Help) */}
  {studios.filter(s => s.bottom).map(studio => (
    <Tooltip title={studio.label} placement="right" key={studio.id}>
      <IconButton size="small" onClick={() => onStudioChange(studio.id)}>
        {studio.icon}
      </IconButton>
    </Tooltip>
  ))}
</Box>
```

**Studios Definition:**
```javascript
const studios = [
  { id: 'home', label: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
  { id: 'emissions', label: 'Emissions', icon: <Co2Icon />, path: '/emissions' },
  { id: 'dataschema', label: 'Data Hub', icon: <StorageIcon />, path: '/dataschema' },
  { id: 'admin', label: 'Admin', icon: <AdminPanelSettingsIcon />, path: '/admin' },
  { id: 'settings', label: 'Settings', icon: <SettingsIcon />, path: '/settings', bottom: true },
  { id: 'help', label: 'Help', icon: <HelpIcon />, path: '/help', bottom: true },
];
```

### 4.5 Status Bar (NEW)

**Create:** `carbon-frontend/src/shell/StatusBar.jsx`

```jsx
<Box sx={{
  height: 22, minHeight: 22,
  bgcolor: 'primary.main',
  color: '#fff',
  display: 'flex',
  alignItems: 'center',
  px: 1.5,
  gap: 1
}}>
  {/* System status */}
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
    <Box sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: statusColor }} />
    <Typography sx={{ fontSize: '0.6875rem', fontWeight: 500 }}>
      {statusLabel}
    </Typography>
  </Box>
  
  <Box sx={{ flex: 1 }} />
  
  {/* Toggle buttons */}
  <Tooltip title="Toggle Sidebar (Ctrl+B)">
    <IconButton 
      size="small"
      onClick={onToggleSidebar}
      sx={{ opacity: sidebarVisible ? 1 : 0.5 }}
    >
      <ViewSidebarIcon sx={{ fontSize: 13 }} />
    </IconButton>
  </Tooltip>
  
  <Tooltip title="Toggle Copilot (Ctrl+\)">
    <IconButton 
      size="small"
      onClick={onToggleCopilot}
      sx={{ opacity: copilotVisible ? 1 : 0.5 }}
    >
      <AutoAwesomeIcon sx={{ fontSize: 13 }} />
    </IconButton>
  </Tooltip>
  
  {/* Version */}
  <Typography sx={{ fontSize: '0.6875rem', opacity: 0.6, ml: 0.5 }}>
    Carbon v1.0
  </Typography>
</Box>
```

**Features:**
- ✅ System status indicator (green=ok, yellow=processing, red=error)
- ✅ Toggle buttons for sidebar/copilot with keyboard shortcuts
- ✅ Version info
- ✅ 22px height (compact)

### 4.6 Pulse Copilot Pane (NEW)

**Create:** `carbon-frontend/src/shell/CopilotPane.jsx`

```jsx
import { useEffect, useRef, useState } from 'react';
import { ensurePulseKey } from '../auth/pulseAuth';

const PULSE_HOST = import.meta.env.VITE_PULSE_HOST || 'http://127.0.0.1:9100';

export default function CopilotPane({ onClose }) {
  const mountRef = useRef(null);
  const [status, setStatus] = useState('loading');
  
  useEffect(() => {
    const el = mountRef.current;
    if (!el || !PULSE_HOST) return;
    
    setStatus('loading');
    
    // Provision per-user pulse_key BEFORE widget connects
    const liveToken = localStorage.getItem('access');
    ensurePulseKey(liveToken)
      .then(() => ensurePulseScript())
      .then((ready) => {
        if (!ready || !window.PulseWidget?.mount) {
          setStatus('unavailable');
          return;
        }
        
        // Mount widget with authenticated identity
        const instance = window.PulseWidget.mount(el, {
          onClose,
          pulseHost: PULSE_HOST,
          instanceId: 'carbon',
          pulseKey: localStorage.getItem('pulse_key'),
          carbonToken: localStorage.getItem('access'),
        });
        
        setStatus('ready');
        return () => instance?.unmount?.();
      });
  }, [onClose]);
  
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div 
        ref={mountRef} 
        style={{ 
          width: '100%', 
          height: '100%', 
          visibility: status === 'ready' ? 'visible' : 'hidden' 
        }} 
      />
      
      {status !== 'ready' && (
        <div style={{ padding: 16, color: '#71717a', fontSize: 12 }}>
          {status === 'loading' ? 'Connecting AI Copilot...' : 'AI Copilot offline'}
        </div>
      )}
    </div>
  );
}
```

**Integration Steps:**
1. Load Pulse widget script from `PULSE_HOST/widget/pulse.js`
2. Provision per-user `pulse_key` via [`ensurePulseKey()`](../auth/pulseAuth.js)
3. Mount widget into pane with authenticated identity
4. Handle offline state gracefully

**Auth Flow:**
```javascript
// carbon-frontend/src/auth/pulseAuth.js
export async function ensurePulseKey(carbonToken) {
  if (!carbonToken) return null;
  
  // Check if already linked
  const existingKey = localStorage.getItem('pulse_key');
  if (existingKey) {
    // Refresh host token (validate still active)
    try {
      const res = await fetch(`${PULSE_HOST}/api/auth/refresh-host-token`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${carbonToken}`
        },
        body: JSON.stringify({ pulse_key: existingKey })
      });
      if (res.ok) return existingKey;
    } catch {}
  }
  
  // Provision new key
  const res = await fetch(`${PULSE_HOST}/api/auth/provision-user`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${carbonToken}`
    },
    body: JSON.stringify({ instance_id: 'carbon' })
  });
  
  const data = await res.json();
  if (data.pulse_key) {
    localStorage.setItem('pulse_key', data.pulse_key);
    return data.pulse_key;
  }
  
  return null;
}
```

### 4.7 Command Palette (NEW)

**Create:** `carbon-frontend/src/shell/CommandPalette.jsx`

```jsx
<Dialog 
  open={open} 
  onClose={onClose}
  maxWidth="sm"
  fullWidth
  PaperProps={{ sx: { borderRadius: 2, mt: 8 } }}
>
  <Box sx={{ p: 2 }}>
    <TextField 
      autoFocus
      fullWidth
      placeholder="Type a command or search..."
      value={query}
      onChange={(e) => setQuery(e.target.value)}
      InputProps={{
        startAdornment: <SearchIcon />
      }}
    />
  </Box>
  
  <Divider />
  
  <List sx={{ maxHeight: 400, overflow: 'auto' }}>
    {filteredCommands.map(cmd => (
      <ListItemButton 
        key={cmd.id}
        onClick={() => { cmd.action(); onClose(); }}
      >
        <ListItemIcon>{cmd.icon}</ListItemIcon>
        <ListItemText 
          primary={cmd.label}
          secondary={cmd.shortcut}
        />
      </ListItemButton>
    ))}
  </List>
</Dialog>
```

**Commands:**
```javascript
const commands = [
  { id: 'toggle-sidebar', label: 'Toggle Sidebar', shortcut: 'Ctrl+B', action: toggleSidebar, icon: <ViewSidebarIcon /> },
  { id: 'toggle-copilot', label: 'Toggle AI Copilot', shortcut: 'Ctrl+\\', action: toggleCopilot, icon: <AutoAwesomeIcon /> },
  { id: 'toggle-theme', label: 'Toggle Theme', action: toggleTheme, icon: <DarkModeIcon /> },
  { id: 'go-dashboard', label: 'Go to Dashboard', action: () => navigate('/dashboard'), icon: <DashboardIcon /> },
  { id: 'go-emissions', label: 'Go to Emissions', action: () => navigate('/emissions'), icon: <Co2Icon /> },
  // ... more commands
];
```

---

## 5. Pulse Widget Integration

### 5.1 Environment Configuration

**Add to `carbon-frontend/.env.example`:**
```bash
# Pulse AI Copilot
VITE_PULSE_HOST=http://127.0.0.1:9100
VITE_PULSE_INSTANCE_ID=carbon
```

**Add to `backend/.env.example`:**
```bash
# Pulse Integration
PULSE_API_URL=http://127.0.0.1:9100/api
PULSE_ADMIN_TOKEN=<provision_from_pulse_admin>
```

### 5.2 Backend Auth Endpoint

**Create:** `backend/accounts/pulse_auth.py`

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import requests
import os

PULSE_API_URL = os.getenv('PULSE_API_URL', 'http://127.0.0.1:9100/api')
PULSE_ADMIN_TOKEN = os.getenv('PULSE_ADMIN_TOKEN', '')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def provision_pulse_user(request):
    """
    Provision a Pulse user identity for the authenticated Carbon user.
    Returns a pulse_key that the frontend stores for widget authentication.
    """
    user = request.user
    instance_id = request.data.get('instance_id', 'carbon')
    
    # Call Pulse API to create/link user
    response = requests.post(
        f'{PULSE_API_URL}/auth/provision-user',
        headers={'Authorization': f'Bearer {PULSE_ADMIN_TOKEN}'},
        json={
            'instance_id': instance_id,
            'host_user_id': str(user.id),
            'host_username': user.username,
            'host_email': user.email,
            'host_token': request.auth.key if hasattr(request.auth, 'key') else str(request.auth),
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        return Response({
            'pulse_key': data.get('pulse_key'),
            'pulse_user_id': data.get('user_id'),
        })
    
    return Response({'error': 'Failed to provision Pulse user'}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def refresh_pulse_token(request):
    """
    Refresh the host token stored in Pulse for ongoing authentication.
    """
    pulse_key = request.data.get('pulse_key')
    
    response = requests.post(
        f'{PULSE_API_URL}/auth/refresh-host-token',
        headers={'Authorization': f'Bearer {PULSE_ADMIN_TOKEN}'},
        json={
            'pulse_key': pulse_key,
            'host_token': request.auth.key if hasattr(request.auth, 'key') else str(request.auth),
        }
    )
    
    return Response(response.json(), status=response.status_code)
```

**Add to `backend/accounts/urls.py`:**
```python
from .pulse_auth import provision_pulse_user, refresh_pulse_token

urlpatterns = [
    # ... existing patterns
    path('api/auth/pulse/provision', provision_pulse_user, name='provision_pulse_user'),
    path('api/auth/pulse/refresh', refresh_pulse_token, name='refresh_pulse_token'),
]
```

### 5.3 Widget Loading Strategy

**Script Loading:**
```javascript
// carbon-frontend/src/shell/ensurePulseScript.js
const PULSE_HOST = import.meta.env.VITE_PULSE_HOST || 'http://127.0.0.1:9100';
const PULSE_SCRIPT_PATHS = ['/widget/pulse.js', '/dist/pulse.js'];

export function ensurePulseScript({ forceReload = false } = {}) {
  if (!PULSE_HOST) return Promise.resolve(false);
  if (window.PulseWidget?.mount && !forceReload) return Promise.resolve(true);
  
  // Remove existing script if force reload
  if (forceReload) {
    const existing = document.querySelector(`script[data-pulse-host="${PULSE_HOST}"]`);
    if (existing) {
      existing.remove();
      delete window.PulseWidget;
    }
  }
  
  return new Promise((resolve) => {
    const urls = PULSE_SCRIPT_PATHS.map(path => `${PULSE_HOST}${path}`);
    
    const tryLoad = (index) => {
      if (index >= urls.length) {
        resolve(false);
        return;
      }
      
      const script = document.createElement('script');
      script.src = urls[index];
      script.defer = true;
      script.dataset.instance = 'carbon';
      script.dataset.pulseHost = PULSE_HOST;
      script.onload = () => resolve(true);
      script.onerror = () => {
        script.remove();
        tryLoad(index + 1);
      };
      document.body.appendChild(script);
    };
    
    tryLoad(0);
  });
}
```

### 5.4 Pulse Button Styles

**Status Bar Toggle:**
```jsx
<Tooltip title="Toggle AI Copilot (Ctrl+\)">
  <IconButton 
    size="small"
    onClick={onToggleCopilot}
    sx={{
      p: 0.25,
      color: 'inherit',
      opacity: copilotVisible ? 1 : 0.5,
      borderRadius: 0.5,
      '&:hover': { 
        opacity: 1, 
        bgcolor: 'rgba(255,255,255,0.15)' 
      }
    }}
  >
    <AutoAwesomeIcon sx={{ fontSize: 13 }} />
  </IconButton>
</Tooltip>
```

**Floating FAB (Optional - if NOT using shell layout):**
```jsx
<Fab 
  color="primary"
  onClick={toggleCopilot}
  sx={{
    position: 'fixed',
    bottom: 24,
    right: 24,
    zIndex: 1000,
    background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
    boxShadow: '0 4px 12px rgba(37, 99, 235, 0.4)',
    '&:hover': {
      background: 'linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%)',
      transform: 'scale(1.05)',
    },
    transition: 'all 200ms ease'
  }}
>
  <AutoAwesomeIcon />
</Fab>
```

---

## 6. Implementation Roadmap

### Phase 1: Shell Foundation (Week 1)

**Goal:** Implement core shell architecture with keyboard shortcuts

**Tasks:**
- [ ] Create [`Shell.jsx`](../carbon-frontend/src/shell/Shell.jsx) component with full layout
- [ ] Create [`ActivityBar.jsx`](../carbon-frontend/src/shell/ActivityBar.jsx) with studio icons
- [ ] Create [`StatusBar.jsx`](../carbon-frontend/src/shell/StatusBar.jsx) with toggle buttons
- [ ] Create [`useShellState.js`](../carbon-frontend/src/shell/useShellState.js) hook for state management
- [ ] Add keyboard shortcuts (Ctrl+B, Ctrl+J, Ctrl+K, Ctrl+\\)
- [ ] Implement localStorage persistence for layout preferences
- [ ] Install `allotment` package for resizable panes: `npm install allotment`
- [ ] Update [`App.jsx`](../carbon-frontend/src/App.jsx) to use Shell layout instead of Layout

**Acceptance Criteria:**
- ✅ Shell renders with all panes visible
- ✅ Sidebar resizable via drag handle (250-360px range)
- ✅ Keyboard shortcuts work (Ctrl+B toggles sidebar)
- ✅ Layout state persists across refreshes

### Phase 2: Header & Footer Polish (Week 1)

**Goal:** Modernize header and footer to Gigacast standards

**Tasks:**
- [ ] Update [`Header.jsx`](../carbon-frontend/src/components/Header.jsx) to 35px compact design
- [ ] Add gradient overlay background
- [ ] Create branded logo pill with border
- [ ] Implement compact action bar (theme toggle + user menu)
- [ ] Create `RoleBadge` component for user roles
- [ ] Create `MenuRow` component for popover menu items
- [ ] Add theme toggle to header (remove from old location)
- [ ] Update [`Footer.jsx`](../carbon-frontend/src/components/Footer.jsx) with links and border
- [ ] Test light/dark mode transitions

**Acceptance Criteria:**
- ✅ Header is 35px tall with gradient overlay
- ✅ User menu shows role badge (admin/org_steward/auditor)
- ✅ Theme toggle works from header
- ✅ Footer has Privacy/Terms/Support links

### Phase 3: Pulse Widget Integration (Week 2)

**Goal:** Integrate Pulse AI copilot widget

**Tasks:**
- [ ] Create [`CopilotPane.jsx`](../carbon-frontend/src/shell/CopilotPane.jsx) component
- [ ] Create [`ensurePulseScript.js`](../carbon-frontend/src/shell/ensurePulseScript.js) loader
- [ ] Create [`pulseAuth.js`](../carbon-frontend/src/auth/pulseAuth.js) auth helper
- [ ] Add VITE_PULSE_HOST to `.env.example`
- [ ] Create backend endpoint [`pulse_auth.py`](../backend/accounts/pulse_auth.py)
- [ ] Add PULSE_API_URL and PULSE_ADMIN_TOKEN to backend `.env.example`
- [ ] Test widget loading and mounting
- [ ] Test authenticated identity (no "Anonymous" state)
- [ ] Test graceful offline handling
- [ ] Add Pulse toggle to status bar

**Acceptance Criteria:**
- ✅ Pulse widget loads when copilot pane opens
- ✅ User identity provisioned before widget connects
- ✅ Widget shows user's name (not "Anonymous")
- ✅ Widget gracefully handles offline Pulse service
- ✅ Pane resizes smoothly (300-600px range)

### Phase 4: Command Palette & Shortcuts (Week 2)

**Goal:** Add VSCode-style command palette

**Tasks:**
- [ ] Create [`CommandPalette.jsx`](../carbon-frontend/src/shell/CommandPalette.jsx) component
- [ ] Define command registry with actions
- [ ] Implement fuzzy search filtering
- [ ] Add Ctrl+K keyboard shortcut
- [ ] Style palette with Gigacast theme
- [ ] Add common commands (navigation, toggles, theme)
- [ ] Test keyboard shortcuts don't conflict with browser

**Acceptance Criteria:**
- ✅ Ctrl+K opens command palette
- ✅ Fuzzy search filters commands
- ✅ Selecting command executes action and closes palette
- ✅ Escape key closes palette

### Phase 5: Enhanced Navigation (Week 3)

**Goal:** Studio-based navigation with activity bar

**Tasks:**
- [ ] Define studio registry (Dashboard, Emissions, Data Hub, Admin, Settings, Help)
- [ ] Implement studio switching logic
- [ ] Sync active studio with current route
- [ ] Create studio-specific sidebar content
- [ ] Add studio icons to activity bar
- [ ] Test deep linking (direct URL to studio)
- [ ] Add studio breadcrumbs to editor area

**Acceptance Criteria:**
- ✅ Clicking activity bar icon navigates to studio
- ✅ Active studio highlights in activity bar
- ✅ Sidebar content updates per studio
- ✅ Direct URLs work (e.g., `/emissions` activates Emissions studio)

### Phase 6: Responsive & Accessibility (Week 3)

**Goal:** Mobile responsiveness and a11y compliance

**Tasks:**
- [ ] Add mobile breakpoints (hide activity bar on small screens)
- [ ] Implement hamburger menu for mobile
- [ ] Add ARIA labels to all interactive elements
- [ ] Test keyboard navigation (Tab, Enter, Escape)
- [ ] Add focus visible styles
- [ ] Test screen reader compatibility
- [ ] Add reduced motion preferences
- [ ] Test color contrast (WCAG AA)

**Acceptance Criteria:**
- ✅ Layout works on tablet (768px)
- ✅ Mobile menu accessible via hamburger
- ✅ All buttons have ARIA labels
- ✅ Keyboard navigation works without mouse
- ✅ Focus indicators visible

### Phase 7: Production Optimization (Week 4)

**Goal:** Performance tuning and production readiness

**Tasks:**
- [ ] Lazy load heavy components (Command Palette, Copilot Pane)
- [ ] Code split by studio (Emissions, Admin separate bundles)
- [ ] Optimize bundle size (tree shaking, minification)
- [ ] Add loading skeletons for slow components
- [ ] Profile render performance (React DevTools)
- [ ] Add error boundaries for shell components
- [ ] Test production build (`npm run build`)
- [ ] Document deployment steps

**Acceptance Criteria:**
- ✅ Initial bundle < 200KB gzipped
- ✅ Shell renders in < 100ms
- ✅ No layout shift during load
- ✅ Error boundaries catch component failures

---

## 7. Design System Updates

### 7.1 Theme Enhancements

**Update:** `carbon-frontend/src/theme/carbonTheme.js`

**Add Custom Component Overrides:**
```javascript
components: {
  // ... existing overrides
  
  MuiIconButton: {
    styleOverrides: {
      root: {
        borderRadius: 4,
        transition: 'all 150ms ease',
        '&:hover': {
          backgroundColor: colors.action.hover,
        },
      },
      sizeSmall: {
        padding: 4,
        '& .MuiSvgIcon-root': { fontSize: 18 },
      },
    },
  },
  
  MuiTooltip: {
    styleOverrides: {
      tooltip: {
        fontSize: '0.6875rem',
        backgroundColor: colors.text.primary,
        padding: '4px 8px',
        borderRadius: 4,
      },
      arrow: {
        color: colors.text.primary,
      },
    },
  },
  
  MuiDrawer: {
    styleOverrides: {
      paper: {
        borderRight: `1px solid ${colors.divider}`,
        backgroundColor: colors.background.paper,
        boxShadow: 'none',
      },
    },
  },
}
```

### 7.2 Z-Index Scale

**Add to theme:**
```javascript
zIndex: {
  mobileStepper: 1000,
  fab: 1050,
  speedDial: 1050,
  appBar: 1100,
  drawer: 1200,
  modal: 1300,
  snackbar: 1400,
  tooltip: 1500,
  copilotPane: 1250, // NEW: between drawer and modal
  statusBar: 1150,   // NEW: between appBar and drawer
  activityBar: 1160, // NEW: above status bar
}
```

### 7.3 Spacing Tokens

**Add custom spacing helpers:**
```javascript
// In theme config
const spacing = (factor) => `${factor * 8}px`;

// Usage in components
sx={{ 
  px: 1.25,  // 10px
  py: 0.375, // 3px
  gap: 0.5,  // 4px
}}
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

**Shell State Hook:**
```javascript
// carbon-frontend/src/shell/__tests__/useShellState.test.js
import { renderHook, act } from '@testing-library/react';
import { useShellState } from '../useShellState';

test('toggles sidebar visibility', () => {
  const { result } = renderHook(() => useShellState());
  
  expect(result.current.sidebarVisible).toBe(true);
  
  act(() => {
    result.current.toggleSidebar();
  });
  
  expect(result.current.sidebarVisible).toBe(false);
});

test('persists layout state to localStorage', () => {
  const { result } = renderHook(() => useShellState());
  
  act(() => {
    result.current.toggleSidebar();
  });
  
  expect(localStorage.getItem('carbon-sidebar-visible')).toBe('false');
});
```

**Pulse Auth:**
```javascript
// carbon-frontend/src/auth/__tests__/pulseAuth.test.js
import { ensurePulseKey } from '../pulseAuth';
import { rest } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  rest.post('http://127.0.0.1:9100/api/auth/provision-user', (req, res, ctx) => {
    return res(ctx.json({ pulse_key: 'test-key-123' }));
  })
);

beforeAll(() => server.listen());
afterAll(() => server.close());

test('provisions pulse key for new user', async () => {
  const key = await ensurePulseKey('carbon-token-abc');
  expect(key).toBe('test-key-123');
  expect(localStorage.getItem('pulse_key')).toBe('test-key-123');
});
```

### 8.2 Integration Tests

**Shell Layout:**
```javascript
// carbon-frontend/src/shell/__tests__/Shell.integration.test.jsx
import { render, screen, fireEvent } from '@testing-library/react';
import { Shell } from '../Shell';

test('renders all shell components', () => {
  render(<Shell />);
  
  expect(screen.getByRole('banner')).toBeInTheDocument(); // Header
  expect(screen.getByRole('navigation')).toBeInTheDocument(); // Activity Bar
  expect(screen.getByRole('complementary')).toBeInTheDocument(); // Sidebar
  expect(screen.getByRole('contentinfo')).toBeInTheDocument(); // Status Bar
});

test('keyboard shortcuts work', () => {
  render(<Shell />);
  
  // Ctrl+B toggles sidebar
  fireEvent.keyDown(window, { key: 'b', ctrlKey: true });
  expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
  
  fireEvent.keyDown(window, { key: 'b', ctrlKey: true });
  expect(screen.getByRole('complementary')).toBeInTheDocument();
});
```

### 8.3 E2E Tests (Playwright)

**Pulse Widget Integration:**
```javascript
// carbon-frontend/e2e/pulse-widget.spec.js
import { test, expect } from '@playwright/test';

test('loads pulse widget in copilot pane', async ({ page }) => {
  await page.goto('http://localhost:5173/dashboard');
  
  // Login
  await page.fill('input[name="username"]', 'admin');
  await page.fill('input[name="password"]', 'admin');
  await page.click('button[type="submit"]');
  
  // Toggle copilot pane
  await page.keyboard.press('Control+\\');
  
  // Wait for widget to load
  await page.waitForSelector('#pulse-widget-root', { timeout: 5000 });
  
  // Check authenticated (no "Anonymous")
  const greeting = await page.textContent('.pulse-greeting');
  expect(greeting).toContain('admin');
  expect(greeting).not.toContain('Anonymous');
});
```

---

## 9. Documentation Requirements

### 9.1 User Guide

**Create:** `docs/USER_GUIDE_UI.md`

```markdown
# Carbon Platform UI Guide

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+K | Open Command Palette |
| Ctrl+B | Toggle Sidebar |
| Ctrl+\ | Toggle AI Copilot |
| Ctrl+, | Open Settings |

## Studios

- **Dashboard**: Executive summary and emissions overview
- **Emissions**: Calculation engine and scope management
- **Data Hub**: Schema admin, data entry, quality
- **Admin**: User management, org units, access control
- **Settings**: Preferences, theme, keyboard shortcuts
- **Help**: Documentation, support, feedback

## AI Copilot (Pulse)

The AI Copilot assists with:
- Carbon accounting questions (GHG Protocol, ISO 14064)
- Data entry guidance (correct units, factors)
- Report interpretation (emissions trends, targets)
- Navigation ("How do I add a facility?")

Access via:
- Status bar button (bottom right)
- Keyboard shortcut: Ctrl+\
- Activity bar icon (if enabled)

## Theme

Toggle light/dark mode:
- Header theme button (sun/moon icon)
- Command Palette → "Toggle Theme"
- Settings → Appearance → Theme
```

### 9.2 Developer Guide

**Create:** `docs/DEV_GUIDE_UI.md`

```markdown
# Carbon UI Development Guide

## Architecture

The UI uses a VSCode-inspired shell layout:

```
App.jsx (Router)
  └── Shell.jsx (Layout)
      ├── Header.jsx (35px topbar)
      ├── ActivityBar.jsx (48px left sidebar)
      ├── Drawer (resizable sidebar)
      │   └── ShellSidebar.jsx (studio-specific nav)
      ├── Allotment (resizable panes)
      │   ├── EditorArea.jsx (Outlet for routes)
      │   └── CopilotPane.jsx (Pulse widget)
      └── StatusBar.jsx (22px bottom bar)
```

## Adding a New Studio

1. Define studio in [`useShellState.js`](../carbon-frontend/src/shell/useShellState.js):
```javascript
const studios = [
  { 
    id: 'reports', 
    label: 'Reports', 
    icon: <AssessmentIcon />, 
    path: '/reports' 
  },
];
```

2. Add route in [`App.jsx`](../carbon-frontend/src/App.jsx):
```javascript
<Route path="/reports" element={<ReportsPage />} />
```

3. Create sidebar content in [`ShellSidebar.jsx`](../carbon-frontend/src/shell/ShellSidebar.jsx):
```javascript
case 'reports':
  return [
    { label: 'Dashboard', path: '/reports' },
    { label: 'Annual Report', path: '/reports/annual' },
    { label: 'Scope Report', path: '/reports/scope' },
  ];
```

## Pulse Widget API

```javascript
// Mount widget
const instance = window.PulseWidget.mount(element, {
  pulseHost: 'http://127.0.0.1:9100',
  instanceId: 'carbon',
  pulseKey: 'user-pulse-key',
  carbonToken: 'user-carbon-token',
  onClose: () => console.log('Widget closed'),
});

// Unmount widget
instance.unmount();
```

## Theme Customization

Modify [`carbonTheme.js`](../carbon-frontend/src/theme/carbonTheme.js):

```javascript
const brandColors = {
  primary: { main: '#2563eb' }, // Change to your brand color
};
```

Supported theme modes: `light`, `dark`

## Testing

```bash
# Unit tests
npm test

# E2E tests
npm run test:e2e

# Component dev (Storybook)
npm run storybook
```
```

---

## 10. Migration Strategy

### 10.1 Backward Compatibility

**Option A: Side-by-Side (Recommended)**
- Keep existing Layout component intact
- Add feature flag: `VITE_USE_SHELL_LAYOUT=true`
- Gradual rollout to users

```javascript
// App.jsx
import { Shell } from './shell/Shell';
import Layout from './components/Layout';

const RootLayout = import.meta.env.VITE_USE_SHELL_LAYOUT === 'true' ? Shell : Layout;

<Route element={<RootLayout />}>
  {/* routes */}
</Route>
```

**Option B: Direct Migration**
- Replace Layout with Shell
- Update all route wrapping
- One-time migration (riskier)

### 10.2 Data Migration

No data migration required - UI changes only.

### 10.3 User Training

**Onboarding Flow:**
1. First login after upgrade → Show "What's New" modal
2. Highlight new features (AI Copilot, keyboard shortcuts, command palette)
3. Offer quick tutorial (skip/take tour)

**Tutorial Checklist:**
- Toggle sidebar (Ctrl+B)
- Open command palette (Ctrl+K)
- Try AI Copilot (Ctrl+\\)
- Switch studios (Activity Bar)
- Change theme (Header button)

---

## 11. Success Metrics

### 11.1 User Experience

- **Task Completion Time**: 20% faster navigation with command palette
- **User Satisfaction**: NPS score > 8 for new UI
- **Feature Adoption**: 60% of users use AI Copilot within first week
- **Error Rate**: < 1% UI-related errors in production

### 11.2 Technical Performance

- **Initial Load**: < 2s to interactive (FCP < 1s)
- **Bundle Size**: < 200KB gzipped for main bundle
- **Lighthouse Score**: > 90 for Performance, Accessibility
- **Shell Render**: < 100ms for shell layout

### 11.3 Development Velocity

- **Component Reusability**: 80% of new features use shell components
- **Design Consistency**: 100% adherence to Gigacast design tokens
- **Onboarding Time**: New developers productive in < 2 days

---

## 12. Risk Mitigation

### 12.1 Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Pulse service offline | High | Graceful degradation, offline message |
| Performance regression | Medium | Bundle analysis, lazy loading, profiling |
| Browser compatibility | Low | Test IE11, Safari, Chrome, Firefox |
| Breaking layout changes | High | Feature flag, gradual rollout |

### 12.2 User Adoption Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Users prefer old UI | Medium | Offer legacy mode toggle for 1 month |
| Learning curve too steep | Medium | Onboarding tutorial, help docs |
| Keyboard shortcuts conflict | Low | Make shortcuts configurable |

---

## 13. Future Enhancements

### 13.1 Phase 2 Features (Q2 2026)

- [ ] Multi-panel layout (split editor area)
- [ ] Customizable activity bar (drag-drop studios)
- [ ] Workspace presets (save/restore layout)
- [ ] Pulse proactive insights (badge notifications)
- [ ] Advanced command palette (recent commands, fuzzy search)

### 13.2 Phase 3 Features (Q3 2026)

- [ ] Collaborative editing (real-time presence)
- [ ] Screen sharing integration
- [ ] Voice commands (Pulse voice input)
- [ ] Mobile native app (React Native)
- [ ] Offline mode (PWA with sync)

---

## 14. References

### 14.1 Design Inspiration

- **Gigacast Platform**: `/home/ahmed/clearturn/gigacast/frontend`
- **VSCode UI**: Activity Bar, Status Bar, Command Palette patterns
- **GitHub UI**: Clean header, footer design
- **Linear UI**: Keyboard-first navigation

### 14.2 Technical Stack

- **React** 18.2+ (Hooks, Suspense)
- **MUI** 5.14+ (Material-UI components)
- **Allotment** 1.19+ (Resizable panes)
- **React Router** 6.20+ (Nested routes)
- **Vite** 5.0+ (Build tool)

### 14.3 Key Files

| File | Purpose |
|------|---------|
| [`Shell.jsx`](../carbon-frontend/src/shell/Shell.jsx) | Root layout component |
| [`ActivityBar.jsx`](../carbon-frontend/src/shell/ActivityBar.jsx) | Studio switcher |
| [`StatusBar.jsx`](../carbon-frontend/src/shell/StatusBar.jsx) | Bottom bar with toggles |
| [`CopilotPane.jsx`](../carbon-frontend/src/shell/CopilotPane.jsx) | Pulse widget container |
| [`useShellState.js`](../carbon-frontend/src/shell/useShellState.js) | Layout state management |
| [`carbonTheme.js`](../carbon-frontend/src/theme/carbonTheme.js) | MUI theme config |

---

## 15. Approval & Sign-Off

**Prepared by:** AI Architect  
**Review Date:** 2026-07-18  
**Status:** Draft - Awaiting User Approval

**Next Steps:**
1. User reviews plan and provides feedback
2. Prioritize phases based on business needs
3. Assign development resources
4. Begin Phase 1: Shell Foundation

**Questions for User:**
1. Do you want side-by-side migration (feature flag) or direct replacement?
2. Which phase should we prioritize first (Shell, Pulse, or Polish)?
3. Are there any Carbon-specific UI elements we should preserve?
4. What's your target timeline for full rollout?

---

**END OF PLAN**
