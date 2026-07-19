// src/pages/catalog/SchemaDetailPage.jsx
// Schema Detail: Full view of a single table with fields, metadata, relations
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Box, Typography, Card, CardContent, CardHeader, Grid, CircularProgress,
  Alert, Chip, Tabs, Tab, Table, TableBody, TableCell, TableHead, TableRow,
  Paper, Button
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import StorageIcon from '@mui/icons-material/Storage';
import { fetchDataSchemaTables, fetchDataSchemaFields } from '../../api/dataschema';
import { fetchTableRelations } from '../../api/catalog';

function TabPanel(props) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

export default function SchemaDetailPage() {
  const { tableId } = useParams();
  const { token } = useAuth();
  const { notify } = useNotification();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [table, setTable] = useState(null);
  const [fields, setFields] = useState([]);
  const [relations, setRelations] = useState([]);
  const [tabIndex, setTabIndex] = useState(0);

  useEffect(() => {
    loadSchemaDetail();
  }, [tableId, token]);

  const loadSchemaDetail = async () => {
    setLoading(true);
    setError(null);
    try {
      const [tableData, fieldsData, relationsData] = await Promise.all([
        fetchDataSchemaTables(token, null, null).then(tables => tables.find(t => t.id === parseInt(tableId))),
        fetchDataSchemaFields(token, tableId, null, null),
        fetchTableRelations(token, { from_table: tableId }).catch(() => []),
      ]);

      if (!tableData) {
        setError('Table not found');
        notify({ message: 'Table not found', type: 'error' });
        return;
      }

      setTable(tableData);
      setFields(fieldsData || []);
      setRelations(relationsData || []);
    } catch (err) {
      const msg = err.message || 'Failed to load schema detail';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!table) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error || 'Table not found'}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <StorageIcon sx={{ fontSize: '2rem', color: 'primary.main' }} />
          <Box>
            <Typography variant="h5" fontWeight={700}>{table.title}</Typography>
            <Typography variant="body2" color="text.secondary">
              {table.description || 'No description'}
            </Typography>
          </Box>
        </Box>
        <Button variant="outlined" startIcon={<EditIcon />}>
          Edit Metadata
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Metadata Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary" display="block">Fields</Typography>
            <Typography variant="h6">{fields.length}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary" display="block">Incoming Relations</Typography>
            <Typography variant="h6">{relations.filter(r => r.to_table === table.id).length}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary" display="block">Outgoing Relations</Typography>
            <Typography variant="h6">{relations.filter(r => r.from_table === table.id).length}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary" display="block">Last Modified</Typography>
            <Typography variant="caption">
              {table.updated_at ? new Date(table.updated_at).toLocaleDateString() : 'N/A'}
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Tabbed Content */}
      <Card>
        <CardHeader
          title="Schema Details"
          titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
        />
        <CardContent sx={{ pt: 0 }}>
          <Tabs value={tabIndex} onChange={(e, v) => setTabIndex(v)} sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
            <Tab label="Fields" />
            <Tab label="Relations" />
          </Tabs>

          {/* Fields Tab */}
          <TabPanel value={tabIndex} index={0}>
            {fields.length === 0 ? (
              <Typography color="text.secondary">No fields defined</Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ backgroundColor: 'action.hover' }}>
                    <TableCell fontWeight={600}>Name</TableCell>
                    <TableCell fontWeight={600}>Type</TableCell>
                    <TableCell fontWeight={600}>Required</TableCell>
                    <TableCell fontWeight={600}>Description</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {fields.map(field => (
                    <TableRow key={field.id}>
                      <TableCell>{field.name}</TableCell>
                      <TableCell>
                        <Chip label={field.field_type} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>{field.required ? 'Yes' : 'No'}</TableCell>
                      <TableCell>{field.description || '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </TabPanel>

          {/* Relations Tab */}
          <TabPanel value={tabIndex} index={1}>
            {relations.length === 0 ? (
              <Typography color="text.secondary">No relations defined</Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ backgroundColor: 'action.hover' }}>
                    <TableCell fontWeight={600}>From Table</TableCell>
                    <TableCell fontWeight={600}>To Table</TableCell>
                    <TableCell fontWeight={600}>Type</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {relations.map(rel => (
                    <TableRow key={rel.id}>
                      <TableCell>{rel.from_table_title}</TableCell>
                      <TableCell>{rel.to_table_title}</TableCell>
                      <TableCell>
                        <Chip label={rel.relation_type} size="small" color="primary" variant="outlined" />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </TabPanel>
        </CardContent>
      </Card>
    </Box>
  );
}
