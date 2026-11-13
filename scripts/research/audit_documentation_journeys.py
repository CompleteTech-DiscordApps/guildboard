#!/usr/bin/env python3
"""Validate a research evidence snapshot; never certifies the product journeys."""
import argparse
import errno
import hashlib
import json
from pathlib import Path

PERSONAS = {'contributor', 'administrator', 'moderator', 'end-user'}
STATES = {'documented', 'partial', 'blocked'}


def audit(root, manifest):
    root = Path(root).resolve()
    errors = []
    if (not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int
            or manifest['schema_version'] != 1):
        return ['unsupported manifest schema'], {}
    journeys = manifest.get('journeys')
    if not isinstance(journeys, list):
        return ['journeys must be a list'], {}
    seen = set()
    counts = {state: 0 for state in sorted(STATES)}
    for journey in journeys:
        if not isinstance(journey, dict):
            errors.append('journey must be an object')
            continue
        persona = journey.get('persona')
        if not isinstance(persona, str) or persona not in PERSONAS or persona in seen:
            errors.append('unknown or duplicate persona')
        elif persona in PERSONAS:
            seen.add(persona)
        steps = journey.get('steps')
        if not isinstance(steps, list) or not steps:
            errors.append('journey must contain steps')
            continue
        for step in steps:
            if not isinstance(step, dict):
                errors.append('step must be an object')
                continue
            state = step.get('state')
            if not isinstance(state, str) or state not in STATES:
                errors.append('unknown step state')
            else:
                counts[state] += 1
            for key in ('action', 'finding', 'next_validation'):
                if not isinstance(step.get(key), str) or not step[key].strip():
                    errors.append(f'missing {key}')
            evidence = step.get('evidence')
            if not isinstance(evidence, list) or not evidence:
                errors.append('step requires evidence')
                continue
            for item in evidence:
                if not isinstance(item, dict) or not isinstance(item.get('path'), str):
                    errors.append('invalid evidence record')
                    continue
                relative = Path(item['path'])
                if relative.is_absolute() or '..' in relative.parts:
                    errors.append('evidence path escapes repository')
                    continue
                try:
                    resolved = (root / relative).resolve(strict=True)
                except FileNotFoundError:
                    errors.append(f'missing evidence: {relative}')
                    continue
                except OSError as exc:
                    if exc.errno == errno.ELOOP:
                        raise ValueError(f'evidence path cannot be resolved: {relative}') from exc
                    raise
                except RuntimeError as exc:
                    raise ValueError(f'evidence path cannot be resolved: {relative}') from exc
                if not resolved.is_relative_to(root):
                    errors.append('evidence path escapes repository')
                    continue
                if not resolved.is_file():
                    errors.append(f'missing evidence: {relative}')
                    continue
                digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
                if digest != item.get('sha256'):
                    errors.append(f'evidence changed: {relative}; re-evaluate finding')
    if seen != PERSONAS:
        errors.append('all four personas are required')
    return errors, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        manifest = json.loads((args.root / 'docs/research/documentation-journeys.json').read_text())
        errors, counts = audit(args.root, manifest)
    except (OSError, ValueError) as exc:
        print(json.dumps({'evidence_valid': False, 'error': str(exc), 'product_verified': False}))
        return 1
    print(json.dumps({'evidence_valid': not errors, 'step_counts': counts, 'errors': errors,
                      'product_verified': False}, indent=2))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
