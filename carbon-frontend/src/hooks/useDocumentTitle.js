import { useEffect } from "react";
import { PLATFORM_NAME } from "../config/branding";

export default function useDocumentTitle(title) {
  useEffect(() => {
    const prev = document.title;
    document.title = title ? `${title} — ${PLATFORM_NAME}` : PLATFORM_NAME;
    return () => { document.title = prev; };
  }, [title]);
}
