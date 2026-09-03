// src/apps/people/referenceDataRegistry.js
// Config-driven registry of reference lists managed by the Reference Data tab.
//
// Adding a NEW reference list = add one entry here (columns + form + CRUD API).
// The generic ReferenceDataManager renders whatever this registry declares, so
// future lists (leave types, contract types, pay grades, …) plug in without
// new page code. Each list is domain-owned config — NOT MDM master data.

import CardGiftcardIcon from '@mui/icons-material/CardGiftcard';
import * as api from '../../api/people';

const BENEFIT_CATEGORIES = ['accommodation', 'vehicle', 'medical', 'school', 'tickets', 'other'];

const CATEGORY_KEYS = {
  accommodation: 'categoryAccommodation',
  vehicle: 'categoryVehicle',
  medical: 'categoryMedical',
  school: 'categorySchool',
  tickets: 'categoryTickets',
  other: 'categoryOther',
};

export const REFERENCE_TYPES = [
  {
    key: 'benefitTypes',
    labelKey: 'referenceBenefitTypes',
    descriptionKey: 'referenceBenefitTypesDesc',
    addLabelKey: 'actionAddBenefitType',
    emptyTitleKey: 'benefitTypesEmpty',
    emptyDescKey: 'benefitTypesEmptyDesc',
    createTitleKey: 'benefitTypeCreateTitle',
    editTitleKey: 'benefitTypeEditTitle',
    savedKey: 'benefitTypeSaved',
    deletedKey: 'benefitTypeDeleted',
    deleteConfirmKey: 'benefitTypeDeleteConfirm',
    icon: CardGiftcardIcon,
    categoryKeys: CATEGORY_KEYS,
    // CRUD API handlers
    list: api.fetchBenefitTypes,
    create: api.createBenefitType,
    update: api.updateBenefitType,
    remove: api.deleteBenefitType,
    // Grid columns (render: text | boolean | status | category)
    columns: [
      { field: 'code', headerKey: 'colCode', tipKey: 'colCodeTip', flex: 1, minWidth: 110 },
      { field: 'name', headerKey: 'colName', tipKey: 'colNameTip', flex: 1.4, minWidth: 160 },
      { field: 'category', headerKey: 'colCategory', tipKey: 'colCategoryTip', flex: 1, minWidth: 130, render: 'category' },
      { field: 'is_eosi_base', headerKey: 'colEosiBase', tipKey: 'colEosiBaseTip', flex: 0.9, minWidth: 110, render: 'boolean' },
      { field: 'is_taxable', headerKey: 'colTaxable', tipKey: 'colTaxableTip', flex: 0.9, minWidth: 100, render: 'boolean' },
      { field: 'is_active', headerKey: 'colActive', tipKey: 'colActiveTip', flex: 0.9, minWidth: 100, render: 'status' },
    ],
    // Form fields (kind: text | select | switch | date)
    form: [
      { name: 'code', labelKey: 'colCode', tipKey: 'colCodeTip', kind: 'text', required: true },
      { name: 'name', labelKey: 'colName', tipKey: 'colNameTip', kind: 'text', required: true },
      {
        name: 'category', labelKey: 'colCategory', tipKey: 'colCategoryTip', kind: 'select',
        required: true, options: BENEFIT_CATEGORIES, optionKeys: CATEGORY_KEYS,
      },
      { name: 'is_eosi_base', labelKey: 'colEosiBase', tipKey: 'colEosiBaseTip', kind: 'switch' },
      { name: 'is_taxable', labelKey: 'colTaxable', tipKey: 'colTaxableTip', kind: 'switch' },
      { name: 'is_active', labelKey: 'colActive', tipKey: 'colActiveTip', kind: 'switch', default: true },
    ],
  },
];
