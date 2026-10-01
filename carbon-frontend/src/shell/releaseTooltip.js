// Lines for the shell status bar and the Pulse status bar.
// Values come from GET /health/ `release`. Empty tag and null built time are omitted.
// Pulse has no version of its own; the release tag is the build, and pack_version
// is the domain pack.

export function shortRelease(tag) {
  const match = String(tag || '').match(/v(\d+\.\d+\.\d+)$/);
  return match ? `v${match[1]}` : 'v1.0';
}

export function releaseTooltip(release) {
  if (!release) return '';
  const lines = [];
  if (release.tag) lines.push(release.tag);
  const pack = [release.pack, release.pack_version].filter(Boolean).join(' ');
  if (pack) lines.push(pack);
  if (release.image_built_at) lines.push(`built ${release.image_built_at}`);
  if (release.process_started_at) lines.push(`started ${release.process_started_at}`);
  else if (release.deployed_at) lines.push(`deployed ${release.deployed_at}`);
  return lines.join('\n');
}

/** Visible Pulse label. A release tag shortens to vX.Y.Z. With no tag, show the
 *  pack identity. Never invent a build number.
 */
export function pulseReleaseLabel(release) {
  if (!release) return '';
  const match = String(release.tag || '').match(/v(\d+\.\d+\.\d+)$/);
  if (match) return `v${match[1]}`;
  if (release.tag) return String(release.tag);
  return [release.pack, release.pack_version].filter(Boolean).join(' ');
}
