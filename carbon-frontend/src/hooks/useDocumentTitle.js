import { useEffect } from "react";
import { PLATFORM_TITLE } from "../config/branding";

export default function useDocumentTitle(title) {
  useEffect(() => {
    const prev = document.title;
    document.title = title ? `${title} — ${PLATFORM_TITLE}` : PLATFORM_TITLE;
    return () => { document.title = prev; };
  }, [title]);
}
