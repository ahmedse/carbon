import React, { useEffect, useMemo, useState } from "react";
import { Link as RouterLink, useSearchParams } from "react-router-dom";
import {
  Box,
  Chip,
  CircularProgress,
  Divider,
  InputAdornment,
  Link as MuiLink,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import DescriptionIcon from "@mui/icons-material/Description";
import DomainIcon from "@mui/icons-material/Domain";
import TableChartIcon from "@mui/icons-material/TableChart";
import MenuBookIcon from "@mui/icons-material/MenuBook";
import { useTranslation } from "react-i18next";
import { useAuth } from "../../auth/AuthContext";
import PageContainer from "../../components/layout/PageContainer";
import { searchCatalog } from "../../api/catalogSearch";

const TYPE_OPTIONS = [
  { key: "all", labelKey: "search.typeAll", icon: SearchIcon },
  { key: "table", labelKey: "search.typeTables", icon: TableChartIcon },
  { key: "field", labelKey: "search.typeFields", icon: DescriptionIcon },
  { key: "domain", labelKey: "search.typeDomains", icon: DomainIcon },
  { key: "glossary", labelKey: "search.typeGlossary", icon: MenuBookIcon },
];

const TYPE_CHIP_META = {
  table: { icon: TableChartIcon, labelKey: "search.table" },
  field: { icon: DescriptionIcon, labelKey: "search.field" },
  domain: { icon: DomainIcon, labelKey: "search.domain" },
  glossary: { icon: MenuBookIcon, labelKey: "search.glossary" },
};

function getResultLink(result) {
  if (result.type === "table") return `/catalog/tables/${result.id}`;
  if (result.type === "domain") return `/catalog/domains/${result.id}`;
  if (result.type === "field") {
    const tableId = result.data_table_id || result.table_id || result.parent_table_id;
    return tableId ? `/catalog/tables/${tableId}` : null;
  }
  return null;
}

export default function SearchPage() {
  const { t } = useTranslation("catalog");
  const { token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  // URL is the single source of truth for query + type filter — no local
  // mirror state, so back/forward navigation and the debounced fetch can never
  // fight over stale copies.
  const query = searchParams.get("q") || "";
  const typeFilter = searchParams.get("types") || "all";
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [errorHint, setErrorHint] = useState("");

  const effectiveTypes = useMemo(() => {
    if (!typeFilter || typeFilter === "all") return [];
    return typeFilter.split(",").filter(Boolean);
  }, [typeFilter]);

  const updateParam = (key, value) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    }, { replace: true });
  };

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(async () => {
      if (!query || query.length < 2) {
        setResults([]);
        setTotal(0);
        setErrorHint(query ? t("search.typeAtLeast2") : "");
        setLoading(false);
        return;
      }

      setLoading(true);
      setErrorHint("");
      try {
        const data = await searchCatalog(token, query, effectiveTypes, 1);
        setResults(Array.isArray(data.results) ? data.results : []);
        setTotal(typeof data.total === "number" ? data.total : 0);
      } catch (error) {
        if (error?.status === 400) {
          setResults([]);
          setTotal(0);
          setErrorHint(t("search.typeAtLeast2"));
        } else {
          setErrorHint(error?.message || t("search.loadError"));
        }
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, [query, effectiveTypes, token, t]);

  const handleQueryChange = (event) => {
    updateParam("q", event.target.value);
  };

  const handleTypeChange = (typeKey) => {
    updateParam("types", typeKey === "all" ? "" : typeKey);
  };

  return (
    <PageContainer>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight={700} sx={{ mb: 1 }}>
          {t("search.title")}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {t("search.subtitle")}
        </Typography>
      </Box>

      <Stack spacing={2}>
        <TextField
          fullWidth
          size="small"
          variant="outlined"
          placeholder={t("searchPlaceholder")}
          value={query}
          onChange={handleQueryChange}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ color: 'text.secondary' }} />
              </InputAdornment>
            ),
          }}
        />

        <Stack direction="row" flexWrap="wrap" gap={1}>
          {TYPE_OPTIONS.map((option) => {
            const Icon = option.icon;
            return (
              <Chip
                key={option.key}
                label={t(option.labelKey)}
                onClick={() => handleTypeChange(option.key)}
                color={typeFilter === option.key ? "primary" : "default"}
                icon={<Icon fontSize="small" />}
                size="small"
              />
            );
          })}
        </Stack>

        {errorHint ? (
          <Typography variant="body2" color="text.secondary">
            {errorHint}
          </Typography>
        ) : null}

        {!errorHint && query && (
          <Typography variant="body2" color="text.secondary">
            {t("search.resultsCount", { count: total, query })}
          </Typography>
        )}

        <Divider />

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={24} />
          </Box>
        ) : results.length === 0 ? (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography variant="subtitle2" color="text.secondary">
              {query && !errorHint ? t("search.noResults") : t("search.enterQuery")}
            </Typography>
          </Box>
        ) : (
          <Stack spacing={2}>
            {results.map((result) => {
              const meta = TYPE_CHIP_META[result.type] || TYPE_CHIP_META.table;
              const Icon = meta.icon;
              const link = getResultLink(result);
              return (
                <Box
                  key={`${result.type}-${result.id}`}
                  sx={{ p: 2, borderRadius: 1, border: 1, borderColor: 'divider', bgcolor: 'background.paper' }}
                >
                  <Stack direction="row" alignItems="flex-start" spacing={1}>
                    <Chip
                      label={t(meta.labelKey)}
                      icon={<Icon fontSize="small" />}
                      size="small"
                    />
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 0.5 }}>
                        {link ? (
                          <MuiLink
                            component={RouterLink}
                            to={link}
                            underline="hover"
                            sx={{ p: 0, textTransform: 'none' }}
                          >
                            {result.name}
                          </MuiLink>
                        ) : (
                          result.name
                        )}
                      </Typography>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
                      >
                        {result.description || t("search.noDescription")}
                      </Typography>
                    </Box>
                  </Stack>
                </Box>
              );
            })}
          </Stack>
        )}
      </Stack>
    </PageContainer>
  );
}
