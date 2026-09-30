import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import useGuide from '../../hooks/useGuide';

const OUTLINE = '2px solid #1976d2';

/**
 * One quiet line offering the next lesson. Silent when there is none, when the guide is
 * unavailable (403/404), or after "Later" (snoozed for a day by the server).
 * When the lesson's `target` exists on this page (`data-guide="<target>"`), it is outlined.
 */
export default function GuideNudge({ appId }) {
  const { t } = useTranslation('guide');
  const navigate = useNavigate();
  const { phase, data, send } = useGuide(appId);
  const [hidden, setHidden] = useState(false);
  const next = data?.lessons?.find((lesson) => lesson.id === data.next_id);

  useEffect(() => {
    if (!next?.target || hidden) return undefined;
    const el = document.querySelector(`[data-guide="${next.target}"]`);
    if (!el) return undefined;
    const previous = el.style.outline;
    el.style.outline = OUTLINE;
    return () => { el.style.outline = previous; };
  }, [next, hidden]);

  if (phase !== 'loaded' || !next || hidden) return null;
  return (
    <Alert
      severity="info"
      data-testid="guide-nudge"
      sx={{ mb: 1 }}
      action={(
        <>
          <Button color="inherit" size="small" onClick={() => navigate(`/guide/${appId}/${next.id}`)}>{t('nudge.start')}</Button>
          <Button
            color="inherit"
            size="small"
            onClick={() => { setHidden(true); send(next.id, { event: 'snooze' }).catch(() => {}); }}
          >
            {t('nudge.later')}
          </Button>
        </>
      )}
    >
      {t('nudge.text', { title: next.title, count: next.minutes })}
    </Alert>
  );
}

GuideNudge.propTypes = { appId: PropTypes.string.isRequired };
