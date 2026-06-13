from typing import List, Dict, Any
from collections import defaultdict

from worldcup_ranker.match_utils import normalise_name, fuzzy_match


def merge_provider_records(providers: Dict[str, List[Dict[str, Any]]], primary: str = 'fbref') -> List[Dict[str, Any]]:
    name_index = {}
    for prov, recs in providers.items():
        if prov.startswith('_'):
            continue
        idx = {}
        for r in recs:
            n = normalise_name(r.get('name') or r.get('player') or '')
            if not n:
                continue
            idx.setdefault(n, []).append(r)
        name_index[prov] = idx

    canonical = []
    seen = set()

    primary_recs = providers.get(primary, [])
    if not primary_recs and providers:
        primary = next(iter(providers.keys()))
        primary_recs = providers[primary]

    all_names = set().union(*[set(idx.keys()) for idx in name_index.values()]) if name_index else set()
    all_names_list = list(all_names)

    for r in primary_recs:
        pname = normalise_name(r.get('name') or r.get('player') or '')
        if not pname or pname in seen:
            continue
        profile = {'names': set(), 'sources': {}, 'minutes': 0, 'matches': 0}
        profile['sources'][primary] = name_index.get(primary, {}).get(pname, [])
        profile['names'].add(pname)

        for prov, idx in name_index.items():
            if prov == primary:
                continue
            if pname in idx:
                profile['sources'][prov] = idx[pname]
                profile['names'].add(pname)
                continue
            matches = fuzzy_match(pname, all_names_list, cutoff=0.88)
            matched = [m for m in matches if m in idx]
            if matched:
                profile['sources'][prov] = idx[matched[0]]
                profile['names'].add(matched[0])

        combined_raw = []
        for prov, recs in profile['sources'].items():
            for rec in recs:
                combined_raw.append({'provider': prov, 'record': rec})
                if prov == primary:
                    try:
                        profile['minutes'] += int(rec.get('minutes') or rec.get('min') or 0)
                    except Exception:
                        pass
                    try:
                        profile['matches'] += int(rec.get('matches') or rec.get('appearances') or rec.get('apps') or 0)
                    except Exception:
                        pass

        profile['raw'] = combined_raw
        profile['canonical_name'] = r.get('name') or r.get('player')

        agg = {
            'minutes': profile['minutes'],
            'matches': profile['matches'],
            'goals': None,
            'assists': None,
            'xG': None,
            'xA': None,
            'overall': None,
            'rating': None,
        }

        vals = {'goals': [], 'assists': [], 'xG': [], 'xA': [], 'overall': [], 'rating': []}
        for item in combined_raw:
            rec = item['record']
            try:
                if rec.get('goals') is not None:
                    vals['goals'].append(float(rec.get('goals') or 0))
            except Exception:
                pass
            try:
                if rec.get('assists') is not None:
                    vals['assists'].append(float(rec.get('assists') or 0))
            except Exception:
                pass
            try:
                if rec.get('xG') is not None:
                    vals['xG'].append(float(rec.get('xG') or 0.0))
            except Exception:
                pass
            try:
                if rec.get('xA') is not None:
                    vals['xA'].append(float(rec.get('xA') or 0.0))
            except Exception:
                pass
            try:
                if rec.get('overall') is not None:
                    vals['overall'].append(float(rec.get('overall')))
            except Exception:
                pass
            try:
                if rec.get('rating') is not None:
                    vals['rating'].append(float(rec.get('rating')))
            except Exception:
                pass

        from statistics import mean
        for k in vals:
            if vals[k]:
                agg[k] = mean(vals[k])

        canonical.append({
            'name': profile['canonical_name'],
            'aliases': sorted(profile['names']),
            'minutes': agg['minutes'],
            'matches': agg['matches'],
            'aggregated': agg,
            'sources': profile['sources'],
            'raw': profile['raw'],
        })
        seen.update(profile['names'])

    for prov, idx in name_index.items():
        for name_key, recs in idx.items():
            if name_key in seen:
                continue
            agg_fallback = {
                'minutes': sum(int(r.get('minutes') or r.get('min') or 0) for r in recs),
                'matches': sum(int(r.get('matches') or r.get('appearances') or r.get('apps') or 0) for r in recs),
                'goals': None, 'assists': None, 'xG': None, 'xA': None, 'overall': None, 'rating': None,
            }
            canonical.append({
                'name': recs[0].get('name') or recs[0].get('player'),
                'aliases': [name_key],
                'minutes': agg_fallback['minutes'],
                'matches': agg_fallback['matches'],
                'aggregated': agg_fallback,
                'sources': {prov: recs},
                'raw': [{'provider': prov, 'record': r} for r in recs],
            })
            seen.add(name_key)

    return canonical
