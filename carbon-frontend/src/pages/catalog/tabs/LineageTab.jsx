import React, { useCallback, useEffect, useMemo, useState } from "react";
import PropTypes from "prop-types";
import { useTranslation } from "react-i18next";
import { useAuth } from "../../../auth/AuthContext";
import { useNotification } from "../../../components/NotificationProvider";
import SystemDialog from "../../../components/SystemDialog";
import EnterpriseGraph from "../../../components/graph/EnterpriseGraph";
import { fetchDataSchemaTables } from "../../../api/dataschema";
import { getTableLineage, getTableImpact, createLineageEdge } from "../../../api/lineage";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  ButtonGroup,
  CircularProgress,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useTheme,
} from "@mui/material";

const GRAPH_VIEW = "graph";
const IMPACT_VIEW = "impact";
const DIRECTIONS = ["upstream", "both", "downstream"];
const EDGE_TYPES = [
  { value: "transform", labelKey: "transform" },
  { value: "copy", labelKey: "copy" },
  { value: "aggregate", labelKey: "aggregate" },
  { value: "dependency", labelKey: "dependency" },
];

function buildGraphNodes(edges, currentTableId, t) {
  const upstreamIds = new Set();
  const downstreamIds = new Set();
  const nodes = [];

  edges.upstream?.forEach((edge) => {
    upstreamIds.add(edge.source_table);
    upstreamIds.add(edge.target_table);
  });
  edges.downstream?.forEach((edge) => {
    downstreamIds.add(edge.source_table);
    downstreamIds.add(edge.target_table);
  });

  const tableMeta = {};
  edges.upstream?.forEach((edge) => {
    tableMeta[edge.source_table] = {
      id: edge.source_table,
      label: edge.source_table_name || t("table"),
      subtitle: edge.source_field_name ? `${edge.source_field_name} → ${edge.target_field_name || ""}` : undefined,
      status: "upstream",
    };
    tableMeta[edge.target_table] = {
      id: edge.target_table,
      label: edge.target_table_name || t("table"),
      subtitle: edge.target_field_name ? `${edge.target_field_name}` : undefined,
      status: edge.target_table === currentTableId ? "current" : "upstream",
    };
  });
  edges.downstream?.forEach((edge) => {
    tableMeta[edge.source_table] = {
      id: edge.source_table,
      label: edge.source_table_name || t("table"),
      subtitle: edge.source_field_name ? `${edge.source_field_name} → ${edge.target_field_name || ""}` : undefined,
      status: edge.source_table === currentTableId ? "current" : "downstream",
    };
    tableMeta[edge.target_table] = {
      id: edge.target_table,
      label: edge.target_table_name || t("table"),
      subtitle: edge.target_field_name ? `${edge.target_field_name}` : undefined,
      status: "downstream",
    };
  });

  // Ensure current table node exists with current status.
  tableMeta[currentTableId] = {
    id: currentTableId,
    label: tableMeta[currentTableId]?.label || t("table"),
    subtitle: tableMeta[currentTableId]?.subtitle,
    status: "current",
  };

  const upstreamNodes = [];
  const currentNodes = [];
  const downstreamNodes = [];

  Object.values(tableMeta).forEach((node) => {
    if (node.id === currentTableId) {
      currentNodes.push(node);
      return;
    }
    if (node.status === "upstream") {
      upstreamNodes.push(node);
    } else if (node.status === "downstream") {
      downstreamNodes.push(node);
    }
  });

  const columnWidth = 280;
  const rowHeight = 100;
  const maxRows = Math.max(upstreamNodes.length, downstreamNodes.length, 1);
  const height = rowHeight * maxRows + 80;

  upstreamNodes.sort((a, b) => a.label.localeCompare(b.label));
  downstreamNodes.sort((a, b) => a.label.localeCompare(b.label));

  upstreamNodes.forEach((node, index) => {
    nodes.push({
      ...node,
      x: 20,
      y: 40 + index * rowHeight,
      w: 240,
      h: 72,
    });
  });

  currentNodes.forEach((node) => {
    nodes.push({
      ...node,
      x: columnWidth + 60,
      y: 40 + ((maxRows - 1) * rowHeight) / 2,
      w: 240,
      h: 88,
    });
  });

  downstreamNodes.forEach((node, index) => {
    nodes.push({
      ...node,
      x: columnWidth * 2 + 100,
      y: 40 + index * rowHeight,
      w: 240,
      h: 72,
    });
  });

  return { nodes, width: columnWidth * 3 + 160, height };
}

function buildGraphEdges(edges) {
  const graphEdges = [];
  (edges.upstream || []).forEach((edge) => {
    graphEdges.push({ source: edge.source_table, target: edge.target_table, label: edge.edge_type });
  });
  (edges.downstream || []).forEach((edge) => {
    graphEdges.push({ source: edge.source_table, target: edge.target_table, label: edge.edge_type });
  });
  return graphEdges;
}

function LineageTab({ tableId, isAdmin }) {
  const { t } = useTranslation("catalog");
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const theme = useTheme();

  const [view, setView] = useState(GRAPH_VIEW);
  const [direction, setDirection] = useState("both");
  const [lineage, setLineage] = useState({ upstream: [], downstream: [] });
  const [impact, setImpact] = useState({ levels: [], total_affected: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [allTables, setAllTables] = useState([]);
  const [edgeForm, setEdgeForm] = useState({ source_table: "", target_table: "", edge_type: "transform", transform_description: "" });
  const [savingEdge, setSavingEdge] = useState(false);

  const loadLineage = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getTableLineage(token, tableId, direction);
      setLineage({
        upstream: Array.isArray(data.upstream) ? data.upstream : [],
        downstream: Array.isArray(data.downstream) ? data.downstream : [],
      });
    } catch (err) {
      setError(err.message || t("lineageLoadError"));
      notifyFromError(err, t("lineageLoadError"));
    } finally {
      setLoading(false);
    }
  }, [token, tableId, direction, notifyFromError, t]);

  const loadImpact = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getTableImpact(token, tableId, 5);
      setImpact({
        levels: Array.isArray(data.levels) ? data.levels : [],
        total_affected: data.total_affected ?? 0,
      });
    } catch (err) {
      setError(err.message || t("impactLoadError"));
      notifyFromError(err, t("impactLoadError"));
    } finally {
      setLoading(false);
    }
  }, [token, tableId, notifyFromError, t]);

  const loadAllTables = useCallback(async () => {
    try {
      const data = await fetchDataSchemaTables(token, null, null);
      setAllTables(Array.isArray(data) ? data : data.results || []);
    } catch (_err) {
      setAllTables([]);
    }
  }, [token]);

  useEffect(() => {
    if (view === GRAPH_VIEW) {
      loadLineage();
    } else {
      loadImpact();
    }
  }, [view, loadLineage, loadImpact]);

  useEffect(() => {
    if (view === GRAPH_VIEW) {
      loadLineage();
    }
  }, [direction, view, loadLineage]);

  useEffect(() => {
    if (isAdmin) {
      loadAllTables();
    }
  }, [isAdmin, loadAllTables]);

  const graphData = useMemo(() => {
    const { nodes, width, height } = buildGraphNodes(lineage, tableId, t);
    return {
      nodes,
      edges: buildGraphEdges(lineage),
      width,
      height,
    };
  }, [lineage, tableId, t]);

  const legend = (
    <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
      <Chip label={t("currentTable")} size="small" color="primary" />
      <Chip label={t("upstreamTables")} size="small" variant="outlined" />
      <Chip label={t("downstreamTables")} size="small" color="secondary" />
    </Stack>
  );

  const nodeColor = useCallback(
    (node) => {
      if (node.status === "current") return theme.palette.primary.main;
      if (node.status === "upstream") return theme.palette.info.main;
      if (node.status === "downstream") return theme.palette.success.main;
      return theme.palette.divider;
    },
    [theme.palette],
  );

  const renderNode = useCallback(
    (node) => (
      <>
        <rect x={6} y={8} width={6} height={node.h - 16} rx={2} fill={nodeColor(node)} />
        <text x={20} y={24} fontSize={12} fontWeight={700} fill={theme.palette.text.primary}>
          {String(node.label).slice(0, 26)}
        </text>
        {node.subtitle && (
          <text x={20} y={42} fontSize={11} fill={theme.palette.text.secondary}>
            {String(node.subtitle).slice(0, 24)}
          </text>
        )}
      </>
    ),
    [nodeColor, theme.palette.text.primary, theme.palette.text.secondary],
  );

  const hasLineage = lineage.upstream.length > 0 || lineage.downstream.length > 0;

  const handleCreateEdge = async () => {
    if (!edgeForm.source_table || !edgeForm.target_table) {
      notify({ message: t("selectSourceAndTarget"), type: "warning" });
      return;
    }
    setSavingEdge(true);
    try {
      await createLineageEdge(token, edgeForm);
      setDialogOpen(false);
      setEdgeForm({ source_table: "", target_table: "", edge_type: "transform", transform_description: "" });
      await loadLineage();
      notify({ message: t("lineageEdgeCreated"), type: "success" });
    } catch (err) {
      notifyFromError(err, t("lineageCreateError"));
    } finally {
      setSavingEdge(false);
    }
  };

  return (
    <Box sx={{ p: 2, minHeight: 360 }}>
      <Stack direction="row" flexWrap="wrap" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <ToggleButtonGroup size="small" exclusive value={view} onChange={(_, value) => value && setView(value)} aria-label={t("viewToggleLabel")}>
          <ToggleButton value={GRAPH_VIEW}>{t("graph")}</ToggleButton>
          <ToggleButton value={IMPACT_VIEW}>{t("impact")}</ToggleButton>
        </ToggleButtonGroup>
        {view === GRAPH_VIEW && (
          <ButtonGroup size="small" aria-label={t("directionToggleLabel")}>
            {DIRECTIONS.map((option) => (
              <Button
                key={option}
                variant={direction === option ? "contained" : "outlined"}
                onClick={() => setDirection(option)}
              >
                {t(option)}
              </Button>
            ))}
          </ButtonGroup>
        )}
        {isAdmin && (
          <Button size="small" variant="contained" onClick={() => setDialogOpen(true)} sx={{ ml: "auto" }}>
            {t("addEdge")}
          </Button>
        )}
      </Stack>

      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: 240 }}>
          <CircularProgress size={28} />
        </Box>
      ) : error ? (
        <Alert severity="error">{error}</Alert>
      ) : view === GRAPH_VIEW ? (
        hasLineage ? (
          <EnterpriseGraph
            nodes={graphData.nodes}
            edges={graphData.edges}
            width={graphData.width}
            layoutHeight={graphData.height}
            height={Math.max(320, graphData.height)}
            nodeColor={nodeColor}
            renderNode={renderNode}
            legend={legend}
            title={t("lineageGraphTitle")}
            summary={t("lineageGraphSummary", { count: graphData.nodes.length })}
            testId="lineage-graph"
          />
        ) : (
          <Box sx={{ p: 4, textAlign: "center" }}>
            <Typography variant="subtitle1" sx={{ mb: 1 }}>
              {t("noLineageRegistered")}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t("addEdgeHint")}
            </Typography>
          </Box>
        )
      ) : (
        <Stack spacing={2}>
          {impact.levels.length === 0 ? (
            <Alert severity="info">{t("noImpactData")}</Alert>
          ) : (
            impact.levels.map((level) => (
              <Box key={level.depth} sx={{ pl: level.depth * 2, borderLeft: "1px solid", borderColor: "divider", py: 1 }}>
                <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                  <Chip label={t("levelCount", { count: level.tables.length })} size="small" />
                  <Typography variant="subtitle2">{t("depthLevel", { depth: level.depth })}</Typography>
                </Stack>
                <Stack spacing={1}>
                  {level.tables.map((table) => (
                    <Box key={table.id} sx={{ p: 1, borderRadius: 1, bgcolor: "action.hover" }}>
                      <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
                        <Box>
                          <Typography variant="body2" fontWeight={600}>
                            {table.name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {table.module_name}
                          </Typography>
                        </Box>
                        <Chip label={t(table.edge_type)} size="small" variant="outlined" />
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              </Box>
            ))
          )}
        </Stack>
      )}

      <SystemDialog
        open={dialogOpen}
        title={t("addLineageEdge")}
        onClose={() => setDialogOpen(false)}
        onCancel={() => setDialogOpen(false)}
        width={520}
        height={420}
        minWidth={420}
        minHeight={380}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button size="small" variant="contained" onClick={handleCreateEdge} disabled={savingEdge}>
            {savingEdge ? t("saving") : t("save")}
          </Button>
        }
      >
        <Stack spacing={2} sx={{ py: 1 }}>
          <Autocomplete
            options={allTables}
            getOptionLabel={(option) => option.title || option.name || String(option.id)}
            value={allTables.find((table) => String(table.id) === String(edgeForm.source_table)) || null}
            onChange={(_, value) => setEdgeForm((current) => ({ ...current, source_table: value?.id || "" }))}
            renderInput={(params) => <TextField {...params} size="small" label={t("sourceTable")} />}
            fullWidth
          />
          <Autocomplete
            options={allTables}
            getOptionLabel={(option) => option.title || option.name || String(option.id)}
            value={allTables.find((table) => String(table.id) === String(edgeForm.target_table)) || null}
            onChange={(_, value) => setEdgeForm((current) => ({ ...current, target_table: value?.id || "" }))}
            renderInput={(params) => <TextField {...params} size="small" label={t("targetTable")} />}
            fullWidth
          />
          <FormControl fullWidth size="small">
            <InputLabel>{t("edgeType")}</InputLabel>
            <Select
              label={t("edgeType")}
              value={edgeForm.edge_type}
              onChange={(event) => setEdgeForm((current) => ({ ...current, edge_type: event.target.value }))}
            >
              {EDGE_TYPES.map((item) => (
                <MenuItem key={item.value} value={item.value}>
                  {t(item.labelKey)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            fullWidth
            size="small"
            multiline
            minRows={3}
            label={t("transformDescription")}
            value={edgeForm.transform_description}
            onChange={(event) => setEdgeForm((current) => ({ ...current, transform_description: event.target.value }))}
          />
        </Stack>
      </SystemDialog>
    </Box>
  );
}

LineageTab.propTypes = {
  tableId: PropTypes.string.isRequired,
  isAdmin: PropTypes.bool,
};

LineageTab.defaultProps = {
  isAdmin: false,
};

export default LineageTab;
