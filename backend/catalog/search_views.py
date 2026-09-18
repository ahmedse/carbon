"""
Full-text search view for catalog resources (tables, fields, domains, glossary).
Uses PostgreSQL SearchVector/SearchQuery/SearchRank for efficient FTS.
"""
from django.db.models import Q, Case, When, Value, CharField, F, DecimalField
from django.db.models.functions import Coalesce
from django.contrib.postgres.search import SearchQuery, SearchRank
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from accounts.permissions import ReadAnyWriteAdmin
from accounts.models import ScopedRole
from dataschema.models import DataTable, DataField
from .models import DataDomain, GlossaryTerm, AssetProfile
from .services import ensure_asset_profiles


class CatalogSearchView(APIView):
    """
    Full-text search across catalog (tables, fields, domains, glossary).

    GET /carbon-api/catalog/search/?q=text&types=table,field,domain,glossary&page=1

    Query params:
    - q: search text (required, min 2 chars)
    - types: comma-separated filter on result types (default: all)
    - page: page number (default: 1, size: 20)

    Response:
    {
        "query": "search text",
        "total": <int>,
        "results": [
            {
                "type": "table|field|domain|glossary",
                "id": <int>,
                "name": "<str>",
                "description": "<str>",
                "url_hint": "<frontend route>"
            },
            ...
        ]
    }
    """
    permission_classes = [ReadAnyWriteAdmin]
    PAGE_SIZE = 20

    def get(self, request):
        # Validate query
        q = (request.query_params.get('q') or '').strip()
        if len(q) < 2:
            return Response(
                {'detail': 'Search query must be at least 2 characters.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse request params
        types_param = request.query_params.get('types', '')
        requested_types = set(t.strip() for t in types_param.split(',') if t.strip()) if types_param else {'table', 'field', 'domain', 'glossary'}
        
        try:
            page = int(request.query_params.get('page', 1))
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1

        # Ensure asset profiles exist for scoping
        ensure_asset_profiles()

        # Scope user's org units (for RBAC filtering)
        user = request.user
        org_unit_ids = None
        if not (user.is_superuser or user.is_staff):
            org_unit_ids = list(
                ScopedRole.objects.filter(
                    user=user, is_active=True
                ).values_list('org_unit_id', flat=True).distinct()
            )
            if not org_unit_ids:
                # User has no scoped roles; return empty results
                return Response({
                    'query': q,
                    'total': 0,
                    'results': []
                })

        # Collect results from each type
        all_results = []

        if 'table' in requested_types:
            all_results.extend(self._search_tables(q, org_unit_ids))

        if 'domain' in requested_types:
            all_results.extend(self._search_domains(q))

        if 'field' in requested_types:
            all_results.extend(self._search_fields(q, org_unit_ids))

        if 'glossary' in requested_types:
            all_results.extend(self._search_glossary(q))

        # Sort by rank (descending)
        all_results.sort(key=lambda x: (-x['rank'], x['id']))

        # Attach trust before trust_tier filter + pagination (ADR-0039 / DTR FE)
        self._attach_trust(all_results)

        trust_tier = (request.query_params.get('trust_tier') or '').strip().lower()
        if trust_tier in ('trusted', 'limited', 'untrustworthy'):
            all_results = [
                r for r in all_results
                if r.get('type') in ('table', 'field') and r.get('trust_tier') == trust_tier
            ]

        total = len(all_results)
        offset = (page - 1) * self.PAGE_SIZE
        paginated_results = all_results[offset:offset + self.PAGE_SIZE]

        # Clear rank field before returning (internal only)
        for result in paginated_results:
            del result['rank']

        return Response({
            'query': q,
            'total': total,
            'trust_tier': trust_tier or None,
            'results': paginated_results
        })

    def _search_tables(self, q, org_unit_ids=None):
        """Search tables using full-text search on search_vector."""
        query = SearchQuery(q)
        qs = DataTable.objects.annotate(
            rank=SearchRank(F('search_vector'), query)
        ).filter(search_vector=query, rank__gt=0)

        # RBAC filtering: only tables in user's org units
        if org_unit_ids is not None:
            qs = qs.filter(module__org_unit_id__in=org_unit_ids)

        results = []
        for table in qs.values('id', 'title', 'description', 'rank', 'module_id'):
            results.append({
                'type': 'table',
                'id': table['id'],
                'name': table['title'],
                'description': table['description'] or '',
                'url_hint': f'/catalog/tables/{table["id"]}',
                'rank': table['rank'],
            })
        return results

    def _search_domains(self, q):
        """Search domains using full-text search on search_vector."""
        query = SearchQuery(q)
        qs = DataDomain.objects.annotate(
            rank=SearchRank(F('search_vector'), query)
        ).filter(search_vector=query, rank__gt=0)

        results = []
        for domain in qs.values('id', 'name', 'description', 'rank'):
            results.append({
                'type': 'domain',
                'id': domain['id'],
                'name': domain['name'],
                'description': domain['description'] or '',
                'url_hint': f'/catalog/domains/{domain["id"]}',
                'rank': domain['rank'],
            })
        return results

    def _search_fields(self, q, org_unit_ids=None):
        """Search fields using icontains (no FTS index)."""
        qs = DataField.objects.filter(
            Q(name__icontains=q) | Q(label__icontains=q) | Q(description__icontains=q)
        ).select_related('data_table__module')

        # RBAC filtering: only fields in tables in user's org units
        if org_unit_ids is not None:
            qs = qs.filter(data_table__module__org_unit_id__in=org_unit_ids)

        results = []
        for field in qs.values('id', 'label', 'description', 'data_table_id', 'data_table__module_id'):
            results.append({
                'type': 'field',
                'id': field['id'],
                'name': field['label'],
                'description': field['description'] or '',
                'data_table_id': field['data_table_id'],
                'url_hint': f'/catalog/tables/{field["data_table_id"]}?field={field["id"]}',
                'rank': 0.0,  # icontains results ranked below FTS
            })
        return results

    def _search_glossary(self, q):
        """Search glossary terms using icontains (no FTS index)."""
        qs = GlossaryTerm.objects.filter(
            Q(term__icontains=q) | Q(definition__icontains=q)
        )

        results = []
        for term in qs.values('id', 'term', 'definition'):
            results.append({
                'type': 'glossary',
                'id': term['id'],
                'name': term['term'],
                'description': term['definition'] or '',
                'url_hint': f'/catalog/metadata#glossary',
                'rank': 0.0,  # icontains results ranked below FTS
            })
        return results

    def _attach_trust(self, results):
        """Attach trust_index / trust_tier to table and field search hits (ADR-0039 + DTR-5)."""
        from .models import AssetProfile
        from .trust_index import (
            batch_freshness_for_table_ids,
            compute_trust_index,
            table_id_for_asset,
        )

        table_ids = [r['id'] for r in results if r.get('type') == 'table']
        field_ids = [r['id'] for r in results if r.get('type') == 'field']
        by_table = {}
        by_field = {}

        if table_ids:
            for profile in AssetProfile.objects.filter(
                data_table_id__in=table_ids, data_field__isnull=True
            ).prefetch_related('tags'):
                by_table[profile.data_table_id] = profile
        if field_ids:
            for profile in AssetProfile.objects.filter(
                data_field_id__in=field_ids
            ).select_related('data_field').prefetch_related('tags'):
                by_field[profile.data_field_id] = profile

        freshness_table_ids = list(table_ids)
        for profile in by_field.values():
            tid = table_id_for_asset(profile)
            if tid:
                freshness_table_ids.append(tid)
        freshness_map = batch_freshness_for_table_ids(freshness_table_ids)

        for result in results:
            profile = None
            if result.get('type') == 'table':
                profile = by_table.get(result['id'])
            elif result.get('type') == 'field':
                profile = by_field.get(result['id'])
            if profile is None:
                result['trust_index'] = None
                result['trust_tier'] = None
                continue
            tid = table_id_for_asset(profile)
            freshness = freshness_map.get(tid) if tid else None
            trust = compute_trust_index(profile, freshness=freshness)
            result['trust_index'] = trust['score']
            result['trust_tier'] = trust['tier']
