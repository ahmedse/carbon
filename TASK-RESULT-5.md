# TASK-RESULT-5.md — DT-2a (RUN 5: Project → OrgUnit)

## Files changed
- backend/mdm/models.py
- backend/mdm/serializers.py
- backend/mdm/views.py
- backend/mdm/admin.py
- backend/accounts/models.py
- backend/accounts/rbac_utils.py
- backend/accounts/permissions.py
- backend/accounts/views.py
- backend/accounts/serializers.py
- backend/accounts/admin.py
- backend/core/models.py
- backend/core/views.py
- backend/core/serializers.py
- backend/core/urls.py
- backend/core/admin.py
- backend/catalog/views.py
- backend/dataschema/views.py
- backend/conftest.py

## Migration output
```text
cd backend && source venv/bin/activate
python manage.py makemigrations mdm accounts core

SystemCheckError: System check identified some issues:

ERRORS:
ai_copilot.ConversationMessage.project: (fields.E300) Field defines a relation with model 'core.Project', which is either not installed, or is abstract.
ai_copilot.ConversationMessage.project: (fields.E307) The field ai_copilot.ConversationMessage.project was declared with a lazy reference to 'core.project', but app 'core' doesn't provide model 'project'.
ai_copilot.ProactiveInsight.project: (fields.E300) Field defines a relation with model 'core.Project', which is either not installed, or is abstract.
ai_copilot.ProactiveInsight.project: (fields.E307) The field ai_copilot.ProactiveInsight.project was declared with a lazy reference to 'core.project', but app 'core' doesn't provide model 'project'.
core.Module.project: (fields.E300) Field defines a relation with model 'core.Project', which is either not installed, or is abstract.
core.Module.project: (fields.E307) The field core.Module.project was declared with a lazy reference to 'core.project', but app 'core' doesn't provide model 'project'.
emissions.Calculation.project: (fields.E300) Field defines a relation with model 'core.Project', which is either not installed, or is abstract.
emissions.Calculation.project: (fields.E307) The field emissions.Calculation.project was declared with a lazy reference to 'core.project', but app 'core' doesn't provide model 'project'.
emissions.ReportingPeriod.project: (fields.E300) Field defines a relation with model 'core.Project', which is either not installed, or is abstract.
emissions.ReportingPeriod.project: (fields.E307) The field emissions.ReportingPeriod.project was declared with a lazy reference to 'core.project', but app 'core' doesn't provide model 'project'.
```

## STEP 21 shell output
Not run; blocked before migration/seed steps.

## Acceptance evidence A–G
Not run; blocked before restart and HTTP validation.

## Deviations
- None; implementation stopped once the hard blocker was confirmed.

## Blockers
- Django cannot start system checks because several existing models still reference core.Project after the Project model was removed from core.models.
- The blocker affects ai_copilot and emissions in addition to core.Module, which exceeds the scope of the requested RUN 5 backend-only refactor.

## Final status: BLOCKED
