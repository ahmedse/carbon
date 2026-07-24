// apps/stub/StubPage.jsx
// Stub App placeholder page — isolation proof only.

export default function StubPage() {
  return (
    <div style={{ padding: 32, fontFamily: 'sans-serif' }}>
      <h2>Stub App</h2>
      <p>
        This page proves a second domain app can register on the platform
        via <code>apps/registry.js</code> with <strong>zero changes</strong> to
        Shell.jsx, ShellSidebar.jsx, or useShellState.js.
      </p>
    </div>
  );
}
