/**
 * Journey art — tiny icons and colours for the trail and the lesson timeline.
 *
 * Display only. Every icon here is chosen by a station's stable `key` (with a
 * positional fallback), so a pack that renames nothing keeps its icon, and a
 * pack that adds a station simply falls back to a flag. No domain wording and
 * no figures live here: the pack owns the words, the engine owns the state.
 */
import TuneIcon from '@mui/icons-material/Tune';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import Inventory2Icon from '@mui/icons-material/Inventory2';
import EditNoteIcon from '@mui/icons-material/EditNote';
import CalculateIcon from '@mui/icons-material/Calculate';
import LockClockIcon from '@mui/icons-material/LockClock';
import AssessmentIcon from '@mui/icons-material/Assessment';
import FlagIcon from '@mui/icons-material/Flag';

const BY_KEY = {
  setup: { Icon: TuneIcon, color: 'info' },
  coverage: { Icon: TrackChangesIcon, color: 'secondary' },
  data_products: { Icon: Inventory2Icon, color: 'warning' },
  data_entry: { Icon: EditNoteIcon, color: 'primary' },
  calculation: { Icon: CalculateIcon, color: 'success' },
  lock: { Icon: LockClockIcon, color: 'warning' },
  report: { Icon: AssessmentIcon, color: 'secondary' },
};

/** The icon + palette colour for one station. Never returns null. */
export function stageArt(station) {
  if (station && BY_KEY[station.key]) return BY_KEY[station.key];
  return { Icon: FlagIcon, color: 'primary' };
}

/** The palette colour for one lesson node, from its real engine state. */
export function lessonTone(lesson) {
  if (lesson?.state === 'done') return 'success';
  if (lesson?.is_next || lesson?.state === 'started') return 'primary';
  return 'default';
}
