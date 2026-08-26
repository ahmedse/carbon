# catalog/services.py
from dataschema.models import DataTable, DataField
from .models import AssetProfile, LineageEdge
from collections import deque


def ensure_asset_profiles():
    """Idempotently create one AssetProfile per DataTable and per DataField."""
    have_tables = set(AssetProfile.objects.filter(data_table__isnull=False).values_list('data_table_id', flat=True))
    have_fields = set(AssetProfile.objects.filter(data_field__isnull=False).values_list('data_field_id', flat=True))
    new = []
    for tid in DataTable.objects.exclude(id__in=have_tables).values_list('id', flat=True):
        new.append(AssetProfile(data_table_id=tid))
    for fid in DataField.objects.exclude(id__in=have_fields).values_list('id', flat=True):
        new.append(AssetProfile(data_field_id=fid))
    if new:
        AssetProfile.objects.bulk_create(new)
    return len(new)


def get_lineage(table_id, direction='both', depth=10):
    """
    Retrieve lineage edges for a given table.
    
    Args:
        table_id: DataTable primary key
        direction: 'upstream' (incoming), 'downstream' (outgoing), or 'both'
        depth: maximum depth to traverse (for future expansion; currently returns all edges)
    
    Returns:
        dict with keys:
        - 'upstream': list of LineageEdge objects where target_table=table_id
        - 'downstream': list of LineageEdge objects where source_table=table_id
    """
    try:
        table = DataTable.objects.get(pk=table_id)
    except DataTable.DoesNotExist:
        return {'upstream': [], 'downstream': []}
    
    result = {'upstream': [], 'downstream': []}
    
    if direction in ('upstream', 'both'):
        result['upstream'] = list(
            LineageEdge.objects.filter(target_table_id=table_id)
            .select_related('source_table', 'target_table', 'source_field', 'target_field')
        )
    
    if direction in ('downstream', 'both'):
        result['downstream'] = list(
            LineageEdge.objects.filter(source_table_id=table_id)
            .select_related('source_table', 'target_table', 'source_field', 'target_field')
        )
    
    return result


def get_impact(table_id, depth=5):
    """
    BFS downstream from a given table to calculate impact (affected tables).
    
    Args:
        table_id: DataTable primary key
        depth: maximum depth to traverse (default 5, capped at 10)
    
    Returns:
        dict with:
        - 'levels': list of {depth, tables} — each table has {id, name, module_name, edge_type}
        - 'total_affected': count of unique affected tables
    """
    depth = min(depth, 10)  # cap at 10
    
    try:
        table = DataTable.objects.get(pk=table_id)
    except DataTable.DoesNotExist:
        return {'levels': [], 'total_affected': 0}
    
    levels = []
    visited = {table_id}
    queue = deque([(table_id, 0)])  # (table_id, current_depth)
    depth_map = {}  # table_id -> (depth, edge_type)
    
    while queue:
        current_id, current_depth = queue.popleft()
        
        if current_depth > depth:
            continue
        
        # Get downstream edges from current table
        edges = LineageEdge.objects.filter(
            source_table_id=current_id
        ).select_related('target_table__module')
        
        for edge in edges:
            target_id = edge.target_table_id
            if target_id not in visited:
                visited.add(target_id)
                depth_map[target_id] = (current_depth + 1, edge.edge_type)
                queue.append((target_id, current_depth + 1))
    
    # Group tables by depth
    by_depth = {}
    for table_id_item, (d, edge_type) in depth_map.items():
        if d not in by_depth:
            by_depth[d] = []
        try:
            table_obj = DataTable.objects.select_related('module').get(pk=table_id_item)
            by_depth[d].append({
                'id': table_obj.id,
                'name': table_obj.title,
                'module_name': table_obj.module.name if table_obj.module else None,
                'edge_type': edge_type
            })
        except DataTable.DoesNotExist:
            pass
    
    # Build levels array (sorted by depth)
    for d in sorted(by_depth.keys()):
        levels.append({
            'depth': d,
            'tables': by_depth[d]
        })
    
    return {
        'levels': levels,
        'total_affected': len(visited) - 1  # exclude the starting table itself
    }
