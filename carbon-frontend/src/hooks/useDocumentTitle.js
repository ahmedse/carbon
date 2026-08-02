import { useEffect } from "react";

const APP_NAME = "Carbon Platform";

export default function useDocumentTitle(title) {
  useEffect(() => {
    const prev = document.title;
    document.title = title ? `${title} — ${APP_NAME}` : APP_NAME;
    return () => { document.title = prev; };
  }, [title]);
}
