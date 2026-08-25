import { createContext } from 'react';

// Language context — value: { lang, isRtl, setLanguage, ready }.
// Lives in its own module so LanguageProvider.jsx / useLanguage.js can each
// export a single thing (react-refresh friendly, matches themeModeContext pattern).
export const LanguageContext = createContext(null);
