// src/pages/admin/GroupDetailPage.jsx
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { Box } from '@mui/material';
import GroupIcon from '@mui/icons-material/Group';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import GroupOverviewTab from './tabs/GroupOverviewTab';
import GroupRoleAssignmentsTab from './tabs/GroupRoleAssignmentsTab';
import GroupEditTab from './tabs/GroupEditTab';
import { fetchGroupDetail } from '../../api/groups';

export default function GroupDetailPage() {
  const { groupId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [group, setGroup] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadGroup = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchGroupDetail(user?.token, groupId);
        setGroup(data);
      } catch (err) {
        setError(err.message || 'Failed to load group');
      } finally {
        setLoading(false);
      }
    };
    if (groupId && user?.token) loadGroup();
  }, [groupId, user?.token]);

  const headerComponent = (
    <DetailHeader
      title={group?.name || 'Group'}
      description={group?.manifest_key || 'Platform role group'}
      icon={GroupIcon}
      onClose={() => navigate('/admin/groups')}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Overview', component: GroupOverviewTab },
        { label: 'Assignment Management', component: GroupRoleAssignmentsTab },
        { label: 'Edit', component: GroupEditTab },
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate('/admin/groups')}
      storageKey='groupDetail'
      entityData={group}
    />
  );
}
