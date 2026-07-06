# MDM / Reference Data

This app provides lightweight reference-data management for bounded schema values.

## Scope
- `ReferenceSet`: a named collection of reference values.
- `ReferenceValue`: a single code/label entry within a set.
- `DataField.reference_set`: optional binding from a dataschema field to a set.

## API
- `GET/POST /carbon-api/mdm/reference-sets/`
- `GET/POST /carbon-api/mdm/reference-values/`
- `POST /carbon-api/mdm/bind-field/`
- `GET /carbon-api/mdm/field-options/`
