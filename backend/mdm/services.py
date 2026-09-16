# File: mdm/services.py
# Service layer for the mdm app (Facade pattern).
# Views call these services; services return plain data (dict/list/queryset),
# never DRF Response objects, and never call self.get_object() — views resolve
# objects and pass them in. Zero behavioral change vs. the logic previously in views.

from django.conf import settings

from .models import ReferenceSet, ReferenceValue, OrgUnit
from .serializers import ReferenceValueSerializer
from catalog.audit_utils import emit_governance_event


# ADR-0028 — deployment identity for instance-gated org seeds
GOFSCO_SEED_BRANDS = frozenset({'gofsco', 'nibras'})
GOFSCO_SEED_INSTANCES = frozenset({'gofsco', 'nibras'})
AASTMT_SEED_BRANDS = frozenset({'aastmt'})
AASTMT_SEED_INSTANCES = frozenset({'aastmt', 'aast'})
_KNOWN_BRANDS = frozenset({'aastmt', 'gofsco', 'nibras', 'medos', 'tectona'})


def get_deployment_root():
    """Return the single active OrgUnit with parent=None, or None if missing.

    Raises RuntimeError if more than one active root exists (ADR-0028
    data corruption — one deployment must have exactly one root).
    """
    roots = list(
        OrgUnit.objects.filter(parent__isnull=True, is_active=True).order_by('id')
    )
    if not roots:
        return None
    if len(roots) > 1:
        ids = [r.id for r in roots]
        raise RuntimeError(
            f"Multiple active OrgUnit roots found (ids={ids}); "
            "ADR-0028 requires exactly one parent=None root per deployment."
        )
    return roots[0]


def get_deployment_org_unit_ids(include_self=True):
    """Descendant id set for the deployment root (empty if no root yet)."""
    root = get_deployment_root()
    if root is None:
        return set()
    return root.get_descendant_ids(include_self=include_self)


def _deployment_identity():
    brand = (getattr(settings, 'DJANGO_BRAND', '') or '').strip().lower()
    instance = (getattr(settings, 'INSTANCE_NAME', '') or '').strip().lower()
    return brand, instance


def is_seed_identity_allowed(allowed_brands, allowed_instances):
    """True if DJANGO_BRAND or INSTANCE_NAME matches the seed's deployment.

    Known brands that are *not* in ``allowed_brands`` refuse even when
    INSTANCE_NAME would otherwise match (avoids default INSTANCE_NAME=AASTMT
    unlocking AASTMT seeds on a nibras brand cell).
    """
    brand, instance = _deployment_identity()
    if brand in allowed_brands:
        return True
    if brand in _KNOWN_BRANDS and brand not in allowed_brands:
        return False
    return instance in allowed_instances


def is_gofsco_org_seed_allowed():
    return is_seed_identity_allowed(GOFSCO_SEED_BRANDS, GOFSCO_SEED_INSTANCES)


def is_aastmt_org_seed_allowed():
    return is_seed_identity_allowed(AASTMT_SEED_BRANDS, AASTMT_SEED_INSTANCES)


class ReferenceSetService:
    """Reference set lifecycle transitions, value management, and bulk ops."""

    @staticmethod
    def transition_set(ref_set, new_state, user=None):
        """
        Advance a reference set through its lifecycle states.
        Returns the transition result dict.
        Raises ValueError({'state': [...]}) on validation/lifecycle errors
        (same messages the view previously raised as DRFValidationError).
        """
        valid_states = [state for state, _ in ReferenceSet.LIFECYCLE_STATES]
        if not new_state:
            raise ValueError({'state': ['This field is required.']})
        if new_state not in valid_states:
            raise ValueError(
                {'state': [f"Invalid state '{new_state}'. Allowed values: {', '.join(valid_states)}"]}
            )
        try:
            ref_set.transition_to(new_state, user=user)
        except ValueError as exc:
            raise ValueError({'state': [str(exc)]})
        return {
            'id': ref_set.id,
            'name': ref_set.name,
            'lifecycle_state': ref_set.lifecycle_state,
            'message': f'Transitioned to {ref_set.lifecycle_state}',
        }

    @staticmethod
    def add_value(ref_set, value_data):
        """
        Add a new reference value to a reference set.
        Returns (serialized_data, created_bool) — the view decides the HTTP status.
        """
        # reference_set is a required serializer field for create; inject it so
        # clients calling add_value don't have to repeat the set id in the body.
        # Use QueryDict.dict() for form/multipart payloads: plain dict(QueryDict)
        # yields lists ({'code': ['X']}) because QueryDict stores multi-values,
        # which the serializer rejects. Plain dicts pass through unchanged.
        if hasattr(value_data, 'dict'):
            data = value_data.dict()
        else:
            data = dict(value_data or {})
        data.setdefault('reference_set', ref_set.id)
        serializer = ReferenceValueSerializer(data=data)
        if serializer.is_valid():
            serializer.save(reference_set=ref_set)
            return serializer.data, True
        return serializer.errors, False

    @staticmethod
    def archive_bulk(ids, user=None):
        """
        Archive multiple reference sets in one pass (is_active=False,
        lifecycle_state=archived). Returns per-item success/failure dict so
        partial failures do not abort the batch.
        """
        results = {'success': [], 'failed': []}
        for set_id in ids:
            try:
                ref_set = ReferenceSet.objects.get(pk=set_id)
            except ReferenceSet.DoesNotExist:
                results['failed'].append({'id': set_id, 'error': 'ReferenceSet not found'})
                continue

            ref_set.is_active = False
            ref_set.lifecycle_state = ReferenceSet.LIFECYCLE_ARCHIVED
            ref_set.save(update_fields=['is_active', 'lifecycle_state'])
            emit_governance_event(
                entity_type='ReferenceSet',
                entity_id=ref_set.id,
                action='delete',
                before={'is_active': True},
                after={'is_active': False, 'lifecycle_state': ReferenceSet.LIFECYCLE_ARCHIVED},
                user=user,
            )
            results['success'].append(ref_set.id)

        return results

    @staticmethod
    def bulk_create(payload, ref_set, user=None):
        """
        Create multiple reference values atomically for a reference set.
        Returns the serialized list of created values.
        Raises ValueError({'error': ..., 'details': ...}) if any item fails validation.
        """
        serializers = []
        for item in payload:
            serializer = ReferenceValueSerializer(data=item)
            if not serializer.is_valid():
                raise ValueError({
                    'error': 'One or more items failed validation',
                    'details': serializer.errors,
                })
            serializer.validated_data['reference_set'] = ref_set
            serializers.append(serializer)

        objs = [s.save() for s in serializers]
        emit_governance_event(
            entity_type='ReferenceValue',
            entity_id=ref_set.id,
            action='create',
            before={},
            after={'bulk_create': len(objs)},
            user=user,
        )
        return ReferenceValueSerializer(objs, many=True).data


class OrgUnitService:
    """Org unit tree and ancestor resolution."""

    @staticmethod
    def get_tree(org_unit):
        """Return the active subtree queryset rooted at org_unit (self included)."""
        children_ids = org_unit.get_descendant_ids(include_self=True)
        return OrgUnit.objects.filter(id__in=children_ids, is_active=True)

    @staticmethod
    def get_ancestors(org_unit):
        """Return the ancestor chain from root to this unit's parent (root-first)."""
        return org_unit.get_ancestors()

    @staticmethod
    def get_deployment_root():
        """Proxy to module-level get_deployment_root (ADR-0028)."""
        return get_deployment_root()
