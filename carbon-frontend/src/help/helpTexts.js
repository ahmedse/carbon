// src/help/helpTexts.js
// Centralized help texts for MicroHelp and other contextual help.
// Easily extendable for i18n.

export const helpTexts = {
  en: {
    "field.order": "Set the position of this field. You can also drag fields to reorder.",
    "field.options": "For select/multiselect fields, add options below as label/value pairs.",
    "field.validation": "You can set validation rules (e.g. required, min, max, regexp). Must be valid JSON.",
    "field.required": "If checked, this field must have a value when entering data.",
    "field.type": "The type determines input (text, number, date, etc). 'Select' will show options.",
    "field.label": "Label seen by users on forms.",
    "field.name": "Internal name (English, no spaces). Used as the key in data.",
    "field.desc": "Internal description (English, no spaces). Used as the field desc in data.",
    "table.desc": "Internal description (English, no spaces). Used as the table desc in data.",
    "table.title": "Internal title (English, no spaces). Used as the table title in data.",
    scope1_microhelp: "Scope 1: Direct greenhouse gas emissions from sources owned or controlled by your organization (e.g., company vehicles, on-site fuel use).",
    scope2_microhelp: "Scope 2: Indirect emissions from the generation of purchased electricity, steam, heating, or cooling consumed by your organization.",
    scope3_microhelp: "Scope 3: All other indirect emissions that occur in your value chain, such as from suppliers, transportation, or product use.",

    "employee.civilId": "Kuwait Civil ID (PACI) — 12 digits. Format is validated; the check digit is not yet enforced.",
    "employee.gender": "Governed enum from the reference data (male / female).",
    "employee.nationality": "Governed enum from the reference data — pick from the list instead of typing.",
    "employee.employeeNo": "Unique employee number. 4–5 digits (e.g. 1024) or two letters + 3 digits (e.g. GF-001).",
    "employee.employmentType": "Governed enum from the reference data (e.g. full_time, part_time).",
    "employee.contractType": "Governed enum from the reference data (e.g. permanent, fixed_term).",
    "employee.rotation": "Rotation pattern code from the reference data (e.g. 1/1, 2/1).",
    "employee.basicSalary": "Reflected monthly basic from the compensation ledger (KWD). Payroll uses verified ledger lines only — change pay on the Pay tab, not this field.",
    
    // ...add more keys as needed
  },
  ar: {
    // Example: "field.order": "حدد موقع هذا الحقل. يمكنك أيضًا سحب الحقول لإعادة الترتيب.",
    // Fill in Arabic strings as needed.

    "employee.civilId": "الرقم المدني الكويتي (PACI) — 12 رقماً. يتم التحقق من الصيغة؛ رقم التحقق لا يُفرَض بعد.",
    "employee.gender": "قيمة محكومة من البيانات المرجعية (ذكر / أنثى).",
    "employee.nationality": "قيمة محكومة من البيانات المرجعية — اختر من القائمة بدلاً من الكتابة اليدوية.",
    "employee.employeeNo": "رقم موظف فريد. 4–5 أرقام (مثال: 1024) أو حرفان + 3 أرقام (مثال: GF-001).",
    "employee.employmentType": "قيمة محكومة من البيانات المرجعية (مثال: دوام كامل، جزئي).",
    "employee.contractType": "قيمة محكومة من البيانات المرجعية (مثال: دائم، محدد المدة).",
    "employee.rotation": "رمز نمط المناوبة من البيانات المرجعية (مثال: 1/1، 2/1).",
    "employee.basicSalary": "الأساسي الشهري المنعكس من سجل التعويضات (د.ك). يعتمد احتساب الرواتب على البنود الموثّقة فقط — غيّر الراتب من تبويب الراتب وليس من هذا الحقل.",
  }
};