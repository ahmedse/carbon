// src/pages/Help.jsx
// Platform (Data Trust) help — brand-aware, rendered from the active brand.
// Each domain app has its own help at /help/:appId (see AppHelp.jsx).

import React from "react";
import useDocumentTitle from "../hooks/useDocumentTitle";
import HelpDocRenderer from "../help/HelpDocRenderer";
import { getPlatformHelpDoc } from "../help/helpDocs";

export default function Help() {
  useDocumentTitle("Help");
  return <HelpDocRenderer doc={getPlatformHelpDoc()} />;
}