#!/usr/bin/env python3
"""Generate usage-data.json for dashboard V3 from local OpenClaw session files."""
import json
from pathlib import Path
from datetime import datetime, UTC
from collections import defaultdict

SESSIONS_META = Path('/root/.openclaw/agents/main/sessions/sessions.json')
OUTPUT = Path('/root/.openclaw/workspace/dashboard-llm-usage/usage-data.json')


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def parse_transcript_usage(path: Path):
    totals = {
        'input': 0,
        'output': 0,
        'cacheRead': 0,
        'cacheWrite': 0,
        'totalTokens': 0,
        'cost': 0.0,
        'messagesWithUsage': 0,
        'providers': set(),
        'models': set(),
        'timeline': []
    }
    if not path.exists():
        return totals

    with path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get('type') != 'message':
                continue
            message = obj.get('message') or {}
            usage = message.get('usage')
            if not usage:
                continue
            totals['messagesWithUsage'] += 1
            totals['input'] += usage.get('input', 0) or 0
            totals['output'] += usage.get('output', 0) or 0
            totals['cacheRead'] += usage.get('cacheRead', 0) or 0
            totals['cacheWrite'] += usage.get('cacheWrite', 0) or 0
            totals['totalTokens'] += usage.get('totalTokens', 0) or 0
            cost = ((usage.get('cost') or {}).get('total')) or 0
            totals['cost'] += float(cost)
            if message.get('provider'):
                totals['providers'].add(message['provider'])
            if message.get('model'):
                totals['models'].add(message['model'])
            totals['timeline'].append({
                'timestamp': obj.get('timestamp'),
                'input': usage.get('input', 0) or 0,
                'output': usage.get('output', 0) or 0,
                'totalTokens': usage.get('totalTokens', 0) or 0,
                'cost': cost,
                'provider': message.get('provider'),
                'model': message.get('model'),
                'role': message.get('role')
            })
    return totals


def session_kind_from_key(key: str):
    if ':subagent:' in key or ':agent:' in key and ':main:' not in key:
        return 'subagent'
    if ':slash:' in key:
        return 'slash'
    if ':direct:' in key:
        return 'main'
    return 'session'


def display_name(key: str, meta: dict):
    origin = meta.get('origin') or {}
    label = origin.get('label')
    if ':subagent:' in key:
        return key.split(':subagent:')[-1]
    if ':slash:' in key:
        return f"Slash · {label or key}"
    if ':direct:' in key:
        return 'Main session'
    return label or key


sessions_meta = load_json(SESSIONS_META) if SESSIONS_META.exists() else {}
all_sessions = []
summary = {
    'sessions': 0,
    'subagents': 0,
    'providers': set(),
    'models': set(),
    'totalTokensKnown': 0,
    'totalInputKnown': 0,
    'totalOutputKnown': 0,
    'cacheRead': 0,
    'cacheWrite': 0,
    'estimatedCost': 0.0,
    'notes': [
        'V3 now reads local OpenClaw session transcripts and aggregates real usage automatically.',
        'Sub-agent rows will appear automatically as soon as OpenClaw stores them in the local session index.',
        'Costs come from transcript usage when the provider reports them; otherwise values stay partial.'
    ]
}
models_breakdown = defaultdict(lambda: {'tokens': 0, 'input': 0, 'output': 0, 'cost': 0.0, 'sessions': 0, 'provider': None})
provider_breakdown = defaultdict(lambda: {'tokens': 0, 'cost': 0.0, 'sessions': 0})
full_timeline = []

for key, meta in sessions_meta.items():
    raw_session_file = meta.get('sessionFile') or meta.get('transcriptPath') or None
    session_file = Path(raw_session_file) if raw_session_file else None
    if session_file is None or (session_file.exists() and session_file.is_dir()) or (session_file is not None and not session_file.exists()):
        sid = meta.get('sessionId')
        candidate = Path('/root/.openclaw/agents/main/sessions') / f'{sid}.jsonl' if sid else None
        if candidate and candidate.exists() and candidate.is_file():
            session_file = candidate
        else:
            session_file = None
    usage = parse_transcript_usage(session_file) if session_file else parse_transcript_usage(Path('/nonexistent'))
    kind = session_kind_from_key(key)
    provider = meta.get('modelProvider') or (next(iter(usage['providers'])) if usage['providers'] else None)
    model = meta.get('model') or (next(iter(usage['models'])) if usage['models'] else None)
    updated_at = meta.get('updatedAt')
    updated_iso = datetime.fromtimestamp(updated_at/1000, UTC).isoformat().replace('+00:00','Z') if updated_at else None
    tokens_total = meta.get('totalTokens') if isinstance(meta.get('totalTokens'), int) else usage['totalTokens']
    entry = {
        'key': key,
        'name': display_name(key, meta),
        'kind': kind,
        'channel': meta.get('lastChannel') or ((meta.get('deliveryContext') or {}).get('channel')),
        'provider': provider,
        'model': model,
        'tokens': {
            'total': tokens_total,
            'input': meta.get('inputTokens') if isinstance(meta.get('inputTokens'), int) else usage['input'],
            'output': meta.get('outputTokens') if isinstance(meta.get('outputTokens'), int) else usage['output'],
            'cached': meta.get('cacheRead') if isinstance(meta.get('cacheRead'), int) else usage['cacheRead'],
            'cachedPercent': round(((meta.get('cacheRead') if isinstance(meta.get('cacheRead'), int) else usage['cacheRead']) / tokens_total) * 100, 1) if tokens_total else None,
            'contextWindow': meta.get('contextTokens'),
        },
        'cost': round(usage['cost'], 6) if usage['cost'] else None,
        'updatedAt': updated_iso,
        'status': 'active',
        'messagesWithUsage': usage['messagesWithUsage']
    }
    all_sessions.append(entry)
    summary['sessions'] += 1
    if kind == 'subagent':
        summary['subagents'] += 1
    summary['totalTokensKnown'] += entry['tokens']['total'] or 0
    summary['totalInputKnown'] += entry['tokens']['input'] or 0
    summary['totalOutputKnown'] += entry['tokens']['output'] or 0
    summary['cacheRead'] += entry['tokens']['cached'] or 0
    summary['cacheWrite'] += usage['cacheWrite'] or 0
    if provider:
        summary['providers'].add(provider)
        provider_breakdown[provider]['tokens'] += entry['tokens']['total'] or 0
        provider_breakdown[provider]['cost'] += usage['cost']
        provider_breakdown[provider]['sessions'] += 1
    if model:
        summary['models'].add(model)
        models_breakdown[model]['tokens'] += entry['tokens']['total'] or 0
        models_breakdown[model]['input'] += entry['tokens']['input'] or 0
        models_breakdown[model]['output'] += entry['tokens']['output'] or 0
        models_breakdown[model]['cost'] += usage['cost']
        models_breakdown[model]['sessions'] += 1
        models_breakdown[model]['provider'] = provider
    summary['estimatedCost'] += usage['cost']
    for point in usage['timeline']:
        point['sessionKey'] = key
        point['sessionName'] = entry['name']
        full_timeline.append(point)

summary['providers'] = sorted(summary['providers'])
summary['models'] = sorted(summary['models'])
summary['estimatedCost'] = round(summary['estimatedCost'], 6) if summary['estimatedCost'] else None
summary['cacheHitPercent'] = round((summary['cacheRead'] / summary['totalTokensKnown']) * 100, 1) if summary['totalTokensKnown'] else None

apis = [
    {'name': 'Gmail API', 'status': 'connected', 'group': 'Google Workspace'},
    {'name': 'Google Calendar API', 'status': 'connected', 'group': 'Google Workspace'},
    {'name': 'Google Drive API', 'status': 'connected', 'group': 'Google Workspace'},
    {'name': 'People API', 'status': 'connected', 'group': 'Google Workspace'},
    {'name': 'Telegram', 'status': 'connected', 'group': 'Messaging'},
    {'name': 'Brave Search', 'status': 'declared-not-verified', 'group': 'Web Search'},
]

out = {
    'generatedAt': datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
    'version': 3,
    'currency': 'USD',
    'pricing': {
        'enabled': True,
        'note': 'Uses provider-reported transcript cost when available in OpenClaw usage records.'
    },
    'summary': summary,
    'sessions': [s for s in all_sessions if s['kind'] != 'subagent'],
    'subagents': [s for s in all_sessions if s['kind'] == 'subagent'],
    'modelsBreakdown': [
        {
            'model': model,
            'provider': data['provider'],
            'tokens': data['tokens'],
            'input': data['input'],
            'output': data['output'],
            'sessions': data['sessions'],
            'estimatedCost': round(data['cost'], 6) if data['cost'] else None,
        }
        for model, data in sorted(models_breakdown.items())
    ],
    'providersBreakdown': [
        {
            'provider': provider,
            'tokens': data['tokens'],
            'sessions': data['sessions'],
            'estimatedCost': round(data['cost'], 6) if data['cost'] else None,
        }
        for provider, data in sorted(provider_breakdown.items())
    ],
    'apis': apis,
    'timeline': sorted(full_timeline, key=lambda x: x.get('timestamp') or ''),
}

OUTPUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'Wrote {OUTPUT}')
print(json.dumps({'sessions': len(out['sessions']), 'subagents': len(out['subagents']), 'timeline': len(out['timeline'])}, ensure_ascii=False))
