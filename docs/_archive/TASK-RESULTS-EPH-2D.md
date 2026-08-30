# TASK-RESULTS-EPH-2D

Files changed:
- carbon-frontend/src/api/catalogSearch.js
- carbon-frontend/src/pages/catalog/SearchPage.jsx
- carbon-frontend/src/App.jsx
- carbon-frontend/src/shell/ShellSidebar.jsx
- carbon-frontend/src/__tests__/SearchPage.test.jsx
- carbon-frontend/src/i18n/locales/en/catalog.json
- carbon-frontend/src/i18n/locales/ar/catalog.json

Exact test names in `carbon-frontend/src/__tests__/SearchPage.test.jsx`:
- renders search input and type chips
- calls searchCatalog after debounce when input changes
- renders results with type chips and links
- updates API types when a filter chip is selected
- shows the empty state when no results are returned
- reads q and types from URL on mount

New i18n keys added:
- en/catalog.json:
  - searchPlaceholder: "Search catalog by name or description..."
  - search.title: "Catalog Search"
  - search.subtitle: "Find tables, fields, domains, and glossary terms."
  - search.typeAll: "All"
  - search.typeTables: "Tables"
  - search.typeFields: "Fields"
  - search.typeDomains: "Domains"
  - search.typeGlossary: "Glossary"
  - search.resultsCount: "{{count}} results for '{{query}}'"
  - search.noResults: "No matching results found."
  - search.enterQuery: "Type at least 2 characters to search."
  - search.typeAtLeast2: "Type at least 2 characters."
  - search.loadError: "Unable to load search results."
  - search.noDescription: "No description available."

- ar/catalog.json:
  - searchPlaceholder: "ابحث في الكتالوج بالاسم أو الوصف..."
  - search.title: "بحث الكتالوج"
  - search.subtitle: "اعثر على الجداول والحقول والنطاقات ومصطلحات المسرد."
  - search.typeAll: "الكل"
  - search.typeTables: "الجداول"
  - search.typeFields: "الحقول"
  - search.typeDomains: "النطاقات"
  - search.typeGlossary: "المسرد"
  - search.resultsCount: "{{count}} نتيجة لـ '{{query}}'"
  - search.noResults: "لم يتم العثور على نتائج مطابقة."
  - search.enterQuery: "اكتب حرفين على الأقل للبحث."
  - search.typeAtLeast2: "اكتب حرفين على الأقل."
  - search.loadError: "تعذر تحميل نتائج البحث."
  - search.noDescription: "لا يوجد وصف متاح."

Notes:
- No `Shell.jsx` update was needed because `/catalog/search` falls under the existing `catalog` studio mapping.
- SearchPage uses `PageContainer` and the shared `apiFetch` helper via `catalogSearch.js`.
