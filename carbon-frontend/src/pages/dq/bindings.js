// carbon-frontend/src/pages/dq/bindings.js
// Resolve JSON-first definition.bindings (table/field NAME strings) into the
// backend's field_assignments_write shape (data_table/data_field IDs).
// The definition keeps human-readable names; the backend requires FK ids.
import { fetchDataSchemaFields } from '../../api/dataschema';

/**
 * @param {object} definition validated schema-v1 rule definition
 * @param {Array<{data_table:number,title?:string,name?:string}>} tables scoped table list
 * @param {string} token
 * @returns {Promise<{assignments: Array<{data_table:number,data_field:number|null}>, errors: Array<{field:string,code:string,message:string}>}>}
 */
export async function resolveBindings(definition, tables, token) {
  const bindings = Array.isArray(definition?.bindings) ? definition.bindings : [];
  const assignments = [];
  const errors = [];
  for (const binding of bindings) {
    const tableName = String(binding?.table ?? '').trim();
    const table = (tables || []).find(
      (t) =>
        String(t.title || t.name || '').toLowerCase() === tableName.toLowerCase() ||
        String(t.table_name || '').toLowerCase() === tableName.toLowerCase()
    );
    if (!table?.data_table) {
      errors.push({
        field: 'bindings',
        code: 'unresolved_table',
        message: `Table "${tableName}" is not in your scope. Available: ${
          (tables || []).map((t) => t.title || t.name).filter(Boolean).join(', ') || 'none'
        }`,
      });
      continue;
    }
    let data_field = null;
    if (binding?.field) {
      const fieldName = String(binding.field).trim();
      let fields = [];
      try {
        const payload = await fetchDataSchemaFields(token, table.data_table, null, null);
        fields = Array.isArray(payload) ? payload : payload?.results || [];
      } catch (_err) {
        fields = [];
      }
      const field = fields.find((f) => f.name === fieldName || f.label === fieldName);
      if (field) {
        data_field = field.id;
      } else {
        errors.push({
          field: 'bindings',
          code: 'unresolved_field',
          message: `Field "${fieldName}" not found on table "${table.title || table.name}".`,
        });
      }
    }
    assignments.push({ data_table: table.data_table, data_field });
  }
  return { assignments, errors };
}
