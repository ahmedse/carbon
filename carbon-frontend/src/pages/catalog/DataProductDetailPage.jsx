// src/pages/catalog/DataProductDetailPage.jsx
// Data Product Detail: BaseDetailPage shell with Overview / Tables / DQ / Edit /
// Audit tabs + metrics panel. Module fetched directly via API (not context — A3 fix).
// AI-toolkit compliant: can() manage gate (CB-13), ConfirmDialog (no window.confirm),
// CB-09 defensive arrays, theme tokens only, shared ProductForm (A7 fix).
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { can } from '../../authz';
import { Box } from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import Inventory2Icon from '@mui/icons-material/Inventory2';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';

import { fetchModule, fetchModuleQualitySummary, fetchModuleAuditTrail } from '../../api/modules';
import { fetchDataSchemaTables } from '../../api/dataschema';
import { fetchAssetProfiles } from '../../api/catalog';
import { fetchOrgUnits } from '../../api/orgUnits';

import DataProductOverviewTab from './tabs/DataProductOverviewTab';
import DataProductTablesTab from './tabs/DataProductTablesTab';
import DataProductDQTab from './tabs/DataProductDQTab';
import DataProductEditTab from './tabs/DataProductEditTab';
import DataProductAuditTab from './tabs/DataProductAuditTab';
import DataProductMetricsPanel from './tabs/DataProductMetricsPanel';

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export default function DataProductDetailPage() {
  useDocumentTitle("Data Product Detail");
  const { moduleId } = useParams();
  const navigate = useNavigate();
  const { token, user, context, availablePerspectives, isGlobalAdminFlag, userCapabilities } = useAuth();
  const { notify } = useNotification();

  const [product, setProduct] = useState(null);
  const [tables, setTables] = useState([]);
  const [assets, setAssets] = useState({});
  const [orgUnits, setOrgUnits] = useState([]);
  const [qualitySummary, setQualitySummary] = useState(null);
  const [auditEvents, setAuditEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const modules = context?.modules || [];

  // manage gate → CATALOG_MANAGE_PRODUCTS (CB-13 — not access_route for admin actions)
  const isAdmin = can(user, 'manage', 'catalog', {
    perspectives: availablePerspectives,
    isGlobalAdminFlag,
    capabilities: userCapabilities,
    modules,
  });

  const loadData = useCallback(async () => {
    if (!moduleId || moduleId === 'new') {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);

      // Module itself is authoritative (A3 — not (context?.modules||[]).find)
      const [moduleData, tablesData, assetsData, orgUnitsData, qualityData, auditData] =
        await Promise.all([
          fetchModule(token, moduleId),
          fetchDataSchemaTables(token, null, moduleId).catch(() => []),
          fetchAssetProfiles(token).catch(() => []),
          fetchOrgUnits(token).catch(() => []),
          fetchModuleQualitySummary(token, moduleId).catch(() => null),
          fetchModuleAuditTrail(token, moduleId).catch(() => []),
        ]);

      setProduct(moduleData);
      setTables(unwrap(tablesData));
      setOrgUnits(unwrap(orgUnitsData));
      setQualitySummary(qualityData || null);

      const assetMap = {};
      unwrap(assetsData).forEach((a) => {
        if (a.data_table != null && !a.data_field) assetMap[a.data_table] = a;
      });
      setAssets(assetMap);
      setAuditEvents(unwrap(auditData));
    } catch (err) {
      const msg = err.message || 'Failed to load data product';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, moduleId, notify]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleDataChanged = useCallback(async () => {
    await loadData();
  }, [loadData]);

  if (!product && !loading && moduleId !== 'new') {
    return (
      <Box sx={{ p: 3 }}>
        <DetailHeader
          title="Data Product Not Found"
          onClose={() => navigate(-1)}
        />
      </Box>
    );
  }

  const headerComponent = product ? (
    <DetailHeader
      title={product.name || 'Data Product'}
      description={product.description || product.org_unit_name || ''}
      icon={Inventory2Icon}
      onClose={() => navigate(-1)}
    />
  ) : (
    <DetailHeader
      title="Loading..."
      icon={Inventory2Icon}
      onClose={() => navigate(-1)}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Overview', component: DataProductOverviewTab },
        { label: 'Tables', component: DataProductTablesTab },
        { label: 'DQ', component: DataProductDQTab },
        ...(isAdmin
          ? [{ label: 'Edit', component: DataProductEditTab }]
          : []),
        { label: 'Audit', component: DataProductAuditTab },
      ]}
      metricsTabs={[
        { label: 'Metrics', component: DataProductMetricsPanel },
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate(-1)}
      storageKey="carbonDataProductDetail"
      entityData={product}
      additionalProps={{
        tables,
        assets,
        orgUnits,
        qualitySummary,
        auditEvents,
        isAdmin,
        onDataChanged: handleDataChanged,
      }}
    />
  );
}
