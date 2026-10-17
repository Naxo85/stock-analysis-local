"""Reconcile a terminated CLI from its own durable event stream, never a guess."""
import json
import uuid


def text(value):
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''


def inspect(events, response):
    result = {'state': 'unknown', 'session_id': None}
    try:
        rows = [json.loads(line) for line in events.splitlines() if line.strip()]
        if not rows or any(not isinstance(row, dict) for row in rows):
            return result
        threads = [str(uuid.UUID(row['thread_id'])) for row in rows if row.get('type') == 'thread.started']
        if len(threads) != 1:
            return result
        result['session_id'] = threads[0]
        starts = [i for i, row in enumerate(rows) if row.get('type') == 'turn.started']
        ends = [i for i, row in enumerate(rows) if row.get('type') in ('turn.completed', 'turn.failed')]
        if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
            return result
        end = ends[0]
        # Later turn/items would make this a different or ambiguous execution.
        if any(row.get('type', '').startswith(('turn.', 'item.')) for row in rows[end + 1:]):
            return result
        final = rows[end]
        if final['type'] == 'turn.failed':
            if isinstance(final.get('error'), dict) and not response.strip():
                result['state'] = 'failed'
            return result
        messages = [row['item'].get('text') for row in rows[starts[0] + 1:end]
                    if row.get('type') == 'item.completed' and isinstance(row.get('item'), dict)
                    and row['item'].get('type') == 'agent_message']
        usage = final.get('usage') or {}
        if (len(messages) != 1 or not isinstance(messages[0], str) or not messages[0].strip()
                or any(type(usage.get(k)) is not int or usage[k] < 0 for k in ('input_tokens', 'output_tokens'))):
            return result
        if response.strip() and response.strip() != messages[0].strip():
            return result
        result.update(state='completed', response=messages[0])
    except (ValueError, TypeError, KeyError, AttributeError):
        pass
    return result
