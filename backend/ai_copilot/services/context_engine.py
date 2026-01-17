"""
Context Engine - Real-time database context for AI
Provides actual project data, modules, tables, and business context
"""

from django.db.models import Q, Count
from asgiref.sync import sync_to_async
from typing import Dict, List, Optional
import json


class ContextEngine:
    """
    Provides real-time context from the application database.
    Makes AI aware of actual project state, data, and structure.
    """
    
    @staticmethod
    async def get_project_context(user, project_id: Optional[int] = None) -> Dict:
        """Get comprehensive project context."""
        from core.models import Project, Module
        from dataschema.models import DataTable, DataField, DataRow
        from accounts.models import ScopedRole
        
        context = {
            "user": {
                "name": user.get_full_name() or user.username,
                "email": user.email,
                "role": None,
            },
            "project": None,
            "modules": [],
            "data_summary": {},
            "available_scopes": [],
            "date_range": {},
        }
        
        # Get user's current project
        if project_id:
            try:
                project = await sync_to_async(Project.objects.get)(id=project_id)
            except Project.DoesNotExist:
                project = None
        else:
            # Get user's first project through their scoped roles
            projects = await sync_to_async(lambda: list(
                Project.objects.filter(
                    scoped_roles__user=user
                ).distinct()[:1]
            ))()
            project = projects[0] if projects else None
        
        if not project:
            return context
        
        # Get user role
        try:
            scoped_role = await sync_to_async(ScopedRole.objects.filter(
                user=user, project=project
            ).select_related('group').first)()
            if scoped_role:
                role_name = await sync_to_async(lambda: scoped_role.group.name)()
                context["user"]["role"] = role_name
            else:
                context["user"]["role"] = "viewer"
        except:
            context["user"]["role"] = "viewer"
        
        # Project info (wrap tenant.name access)
        tenant_name = await sync_to_async(lambda: project.tenant.name)()
        context["project"] = {
            "id": project.id,
            "name": project.name,
            "tenant": tenant_name,
        }
        
        # Get modules for this project
        modules = await sync_to_async(lambda: list(
            Module.objects.filter(
                project=project
            ).order_by('scope', 'name')
        ))()
        
        context["modules"] = [
            {
                "id": m.id,
                "name": m.name,
                "scope": m.scope,
            }
            for m in modules
        ]
        
        # Get aggregated data summary efficiently
        def get_data_summary():
            """Efficiently aggregate data using database queries."""
            from django.db.models import Count, Min, Max, Q
            
            # Get table counts and row counts per scope
            tables = DataTable.objects.filter(
                module__project=project
            ).select_related('module').prefetch_related('fields', 'rows')
            
            scope_summary = {}
            all_years = set()
            all_months = set()
            all_days = set()
            earliest_created = None
            latest_updated = None
            total_rows = 0
            
            for table in tables:
                scope = table.module.scope
                if scope not in scope_summary:
                    scope_summary[scope] = {
                        "tables": 0,
                        "total_rows": 0,
                        "complete_rows": 0,
                        "missing_required": 0,
                    }
                
                scope_summary[scope]["tables"] += 1
                row_count = table.rows.count()
                scope_summary[scope]["total_rows"] += row_count
                total_rows += row_count
                
                # Get required fields
                required_fields = list(
                    table.fields.filter(required=True, is_active=True)
                    .values_list('name', flat=True)
                )
                
                # Analyze rows for completeness and date extraction
                if required_fields:
                    rows = table.rows.all()
                    for row in rows:
                        values = row.values or {}
                        
                        # Extract date fields
                        if 'reporting_year' in values and values['reporting_year']:
                            all_years.add(values['reporting_year'])
                        if 'reporting_month' in values and values['reporting_month']:
                            all_months.add(values['reporting_month'])
                        if 'reporting_day' in values and values['reporting_day']:
                            all_days.add(values['reporting_day'])
                        if 'date' in values and values['date']:
                            all_years.add(values['date'][:4] if len(str(values['date'])) >= 4 else None)
                        
                        # Track system timestamps
                        if not earliest_created or row.created_at < earliest_created:
                            earliest_created = row.created_at
                        if not latest_updated or row.updated_at > latest_updated:
                            latest_updated = row.updated_at
                        
                        # Check data completeness
                        is_complete = all(
                            values.get(field) not in (None, '', [])
                            for field in required_fields
                        )
                        if is_complete:
                            scope_summary[scope]["complete_rows"] += 1
                        else:
                            scope_summary[scope]["missing_required"] += 1
            
            return {
                "scope_summary": scope_summary,
                "date_info": {
                    "total_records": total_rows,
                    "reporting_years": sorted([y for y in all_years if y]),
                    "reporting_months": sorted(list(all_months)),
                    "reporting_days": sorted([d for d in all_days if d]),
                    "earliest_created": earliest_created.isoformat() if earliest_created else None,
                    "latest_updated": latest_updated.isoformat() if latest_updated else None,
                }
            }
        
        # Execute data summary
        summary = await sync_to_async(get_data_summary)()
        
        context["data_summary"] = summary["scope_summary"]
        context["available_scopes"] = list(summary["scope_summary"].keys())
        context["date_range"] = summary["date_info"]
        
        return context
    
    @staticmethod
    async def get_data_quality_context(user, project_id: Optional[int] = None) -> str:
        """Get human-readable data quality summary."""
        from core.models import Project
        from dataschema.models import DataTable, DataField, DataRow
        
        if not project_id:
            return "No project selected."
        
        try:
            project = await sync_to_async(Project.objects.get)(id=project_id)
        except:
            return "Project not found."
        
        # Get tables with missing required data
        tables = await sync_to_async(lambda p=project: list(
            DataTable.objects.filter(
                module__project=p
            ).select_related('module')
        ))()
        
        issues = []
        for table in tables:
            # Get table and module names safely
            table_title = await sync_to_async(lambda t=table: t.title)()
            module_name = await sync_to_async(lambda t=table: t.module.name)()
            
            required_fields = await sync_to_async(lambda t=table: list(
                DataField.objects.filter(
                    data_table=t,
                    required=True
                ).values_list('name', flat=True)
            ))()
            
            if required_fields:
                rows = await sync_to_async(lambda t=table: list(
                    DataRow.objects.filter(data_table=t).values('id', 'values')
                ))()
                
                missing_count = 0
                for row in rows:
                    data = row['values'] or {}
                    has_missing = any(
                        data.get(field) in (None, '', [])
                        for field in required_fields
                    )
                    if has_missing:
                        missing_count += 1
                
                if missing_count > 0:
                    issues.append(
                        f"- {module_name} / {table_title}: "
                        f"{missing_count} rows with missing required fields"
                    )
        
        if not issues:
            return f"Project '{project.name}': All data complete ✓"
        
        return f"Project '{project.name}' data quality issues:\n" + "\n".join(issues)
    
    @staticmethod
    def format_context_for_prompt(context: Dict) -> str:
        """Format context dictionary into readable prompt text with visual structure."""
        lines = []
        
        # Header
        lines.append("=" * 60)
        lines.append("CARBON EMISSIONS DATA CONTEXT")
        lines.append("=" * 60)
        
        if context.get("project"):
            proj = context["project"]
            lines.append(f"\n📊 PROJECT: {proj['name']}")
            lines.append(f"   Organization: {proj['tenant']}")
        
        if context.get("user"):
            user = context["user"]
            lines.append(f"\n👤 USER: {user['name']} ({user['role']})")
            lines.append(f"   Email: {user['email']}")
        
        if context.get("modules"):
            lines.append(f"\n🔧 ENABLED MODULES ({len(context['modules'])}):")
            scope_groups = {}
            for mod in context["modules"]:
                scope = mod['scope']
                if scope not in scope_groups:
                    scope_groups[scope] = []
                scope_groups[scope].append(mod['name'])
            
            for scope in sorted(scope_groups.keys()):
                lines.append(f"   Scope {scope}: {', '.join(scope_groups[scope])}")
        
        if context.get("date_range"):
            date_range = context["date_range"]
            lines.append(f"\n📅 DATA TIMELINE:")
            lines.append(f"   Total Records: {date_range['total_records']:,}")
            if date_range['reporting_years']:
                years = date_range['reporting_years']
                lines.append(f"   Reporting Years: {min(years)} → {max(years)}")
            if date_range['reporting_months']:
                unique_months = sorted(set(date_range['reporting_months']))
                lines.append(f"   Months Covered: {', '.join(unique_months[:6])}" + 
                           (f" (+{len(unique_months)-6} more)" if len(unique_months) > 6 else ""))
            if date_range.get('reporting_days') and date_range['reporting_days']:
                lines.append(f"   Days Recorded: {len(date_range['reporting_days'])} unique days")
            if date_range['earliest_created']:
                lines.append(f"   First Entry: {date_range['earliest_created'][:10]}")
            if date_range['latest_updated']:
                lines.append(f"   Last Update: {date_range['latest_updated'][:10]}")
        
        if context.get("data_summary"):
            lines.append(f"\n📈 DATA QUALITY BY SCOPE:")
            for scope, data in sorted(context["data_summary"].items()):
                completeness = (
                    data['complete_rows'] / data['total_rows'] * 100
                    if data['total_rows'] > 0 else 0
                )
                status = "✓" if completeness >= 95 else "⚠" if completeness >= 80 else "✗"
                lines.append(
                    f"   {status} Scope {scope}: {data['tables']} tables, "
                    f"{data['total_rows']:,} rows ({completeness:.1f}% complete)"
                )
                if data['missing_required'] > 0:
                    lines.append(f"      → {data['missing_required']} rows need attention")
        
        lines.append("\n" + "=" * 60)

# Global instance
_context_engine = None

def get_context_engine() -> ContextEngine:
    """Get or create context engine instance."""
    global _context_engine
    if _context_engine is None:
        _context_engine = ContextEngine()
    return _context_engine
