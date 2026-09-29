"""Missing-value handling for provisional ATS inputs, without changing source data."""
import ast
import math
import json

MISSING_MARKERS = {'', 'null', 'none', 'nan', 'n/a', 'na', 'not available'}


def _text(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ''
    if isinstance(value, (list, tuple)):
        return ', '.join(part for item in value if (part := _text(item)))
    if not isinstance(value, str):
        raise ValueError('Qualification fields must contain text, a list of text, or a missing value.')
    value = value.strip()
    if value.casefold() in MISSING_MARKERS:
        return ''
    # The structured resume source stores Python-style lists as CSV text.
    if value.startswith('[') and value.endswith(']'):
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            try:
                parsed = json.loads(value)
            except ValueError:
                parsed = None
        if isinstance(parsed, list):
            return _text(parsed)
    return ' '.join(value.split())


def prepare_records(records, id_field, text_fields, *, missing_policy='error'):
    """Return (prepared records, audit records) for explicitly selected text fields.

    error: stop on any missing selected field.
    skip_missing: omit missing fields and skip rows with no usable text.
    Both modes produce provisional inputs, not certified clean study data.
    """
    if missing_policy not in ('error', 'skip_missing'):
        raise ValueError('missing_policy must be error or skip_missing.')
    if not text_fields or isinstance(text_fields, str) or len(set(text_fields)) != len(text_fields):
        raise ValueError('text_fields must be a nonempty list of distinct field names.')
    prepared, audit, seen = [], [], set()
    for row in records:
        identifier = row.get(id_field)
        if not isinstance(identifier, str) or identifier.strip().casefold() in MISSING_MARKERS:
            raise ValueError(f'Missing or invalid identifier in {id_field}.')
        identifier = identifier.strip()
        if identifier in seen:
            raise ValueError(f'Found duplicate identifier: {identifier}')
        seen.add(identifier)
        values = [(field, _text(row.get(field))) for field in text_fields]
        missing = [field for field, value in values if not value]
        text = '\n'.join(f'{field}: {value}' for field, value in values if value)
        if missing_policy == 'error' and missing:
            raise ValueError(f'{identifier}: missing selected fields: {", ".join(missing)}')
        action = 'skipped' if not text else ('kept_partial' if missing else 'kept')
        audit.append({'record_id': identifier, 'action': action,
                      'reason': 'no_usable_text' if not text else ('missing_fields_omitted' if missing else 'usable_text'),
                      'missing_fields': missing, 'missing_policy': missing_policy})
        if text:
            prepared.append({id_field: identifier, 'text': text, 'missing_fields': missing,
                             'missing_policy': missing_policy, 'input_status': 'provisional'})
    return prepared, audit
