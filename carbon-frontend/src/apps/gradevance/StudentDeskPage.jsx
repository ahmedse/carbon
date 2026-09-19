// QUARANTINED (ADR-0042 / Instrument Trust L4).
// Legacy GradeVance student desk — Learn owns the student surface via /learn + me/*.
// Do not revive routes or imports. Kept as a redirect stub so any stale deep link lands on Learn.

import { Navigate } from 'react-router-dom';

export default function StudentDeskPage() {
  return <Navigate to="/learn" replace />;
}
