import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useAuth } from '../auth/AuthContext';
import { fetchGuide, postGuideEvent } from '../api/guide';

/** Guide listing for one app. `send` posts an event and refreshes the listing. */
export default function useGuide(appId) {
  const { token } = useAuth();
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('ar') ? 'ar' : 'en';
  const [phase, setPhase] = useState('loading');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const body = await fetchGuide(appId, { lang, token });
      setData(body && typeof body === 'object' ? body : null);
      setError('');
      setPhase('loaded');
    } catch (err) {
      setData(null);
      setError(err?.message || '');
      setPhase('error');
    }
  }, [appId, lang, token]);

  useEffect(() => {
    load();
  }, [load]);

  const send = useCallback(async (lessonId, body) => {
    const out = await postGuideEvent(appId, lessonId, body, token);
    await load();
    return out;
  }, [appId, token, load]);

  return { phase, data, error, reload: load, send, lang, token };
}
