#!/usr/bin/env python3
"""Prune the public archive to a rolling window.

WHY
The archive grows about 4 MB a day. Two separate reasons to bound what the
public repository carries:

  1. Data rights. Kalshi's terms name "providing archived or cached data sets
     containing Kalshi Data to another person or entity". A continuously growing
     raw feed is that; a bounded research sample is a much weaker version of it.
     See docs/DATA_SOURCES.md.
  2. Size. Unbounded, the working tree reaches roughly 1.44 GB in a year against
     GitHub's 1 GB guidance.

WHAT THIS DOES NOT DO — read this before believing the size argument
Deleting a file in a new commit does not remove it from git history. The blob
stays, so `.git` keeps growing at the same rate and a full `git clone` still
downloads everything ever committed. This script bounds the WORKING TREE, not
the repository. Anyone browsing the repo, or doing a shallow clone, sees the
window; anyone doing a full clone does not.

Bounding the repository itself would take either periodic history rewriting, or
never committing raw vendor data to the public repo at all. Both are real
options and neither is done here. The claim is limited to what is measured.

ORDER MATTERS, AND THE WORKFLOW ENFORCES IT
Pruning runs only after the private mirror has been updated SUCCESSFULLY. The
mirror step exits 0 even when it is skipped for a missing token, so "the
previous step passed" is not proof; the workflow sets MIRROR_OK=1 only on the
real push path and the prune step is gated on that. If the mirror is skipped,
pruning is skipped too. Otherwise the data is gone from both places at once.

Usage:
    python scripts/prune_archive.py             # dry run, prints what would go
    python scripts/prune_archive.py --apply     # delete
"""
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'raw')
POINTER = os.path.join(ROOT, 'state', 'latest.json')

ARCHIVE_DAYS = 14          # how many days of day-folders to keep
DAY = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# If a bug in date handling ever asked to delete most of the archive, refuse.
# One day per run is the expected steady state.
MAX_SHARE_DELETED = 0.5


def day_dirs():
    """Every YYYY-MM-DD folder under raw/, at any depth.

    The depth varies: most streams are raw/<stream>/<day>/, but trades are
    raw/events/trades/<day>/. Matching on the folder name rather than the path
    shape means a new stream does not need this script changed.
    """
    out = []
    for base, dirs, _ in os.walk(RAW):
        for d in list(dirs):
            if DAY.match(d):
                out.append(os.path.join(base, d))
                dirs.remove(d)          # do not descend into a day folder
    return sorted(out)


def size_of(path):
    total = 0
    for base, _, names in os.walk(path):
        for n in names:
            try:
                total += os.path.getsize(os.path.join(base, n))
            except OSError:
                pass
    return total


def refresh_pointer():
    """Recompute the archive counters in state/latest.json.

    The collector writes those counters from disk during the snapshot step,
    which happens BEFORE this script runs. Without this, the pointer reports one
    day more than the repository actually holds and the dateline on the page
    shows a number no file backs up. Measured on 2026-09-14: the archive was 14
    days and the pointer said 15.

    Only the archive block is touched. The snapshot fields — stamp, paths,
    sync window — describe the run that just happened and stay as written.
    """
    if not os.path.isfile(POINTER):
        return None
    meta_root = os.path.join(RAW, '_meta')
    per_day = {}
    if os.path.isdir(meta_root):
        for d in sorted(os.listdir(meta_root)):
            dp = os.path.join(meta_root, d)
            if DAY.match(d) and os.path.isdir(dp):
                per_day[d] = len([x for x in os.listdir(dp) if x.endswith('.json')])
    days = sorted(per_day)
    with open(POINTER, encoding='utf-8') as f:
        ptr = json.load(f)
    before = (ptr.get('archive') or {}).get('day_count')
    ptr['archive'] = {
        'day_count': len(per_day),
        'snapshot_count': sum(per_day.values()),
        'first_day': days[0] if days else None,
        'last_day': days[-1] if days else None,
        'per_day': per_day,
    }
    with open(POINTER, 'w', encoding='utf-8') as f:
        json.dump(ptr, f, ensure_ascii=False, indent=1)
    return before, ptr['archive']['day_count'], ptr['archive']['snapshot_count']


def main():
    apply = '--apply' in sys.argv

    meta_root = os.path.join(RAW, '_meta')
    if not os.path.isdir(meta_root):
        print('raw/_meta is absent — nothing to do.')
        return 0

    # _meta is the authoritative record of which days a run happened on, so the
    # cutoff is computed from it and then applied to every stream. Using each
    # stream's own days would drift them apart: holders runs once a day and
    # kalshi only started on 2026-08-31.
    meta_days = sorted(d for d in os.listdir(meta_root) if DAY.match(d))
    print('ARCHIVE PRUNE%s' % ('' if apply else '  (DRY RUN, nothing deleted)'))
    print('window      : %d days' % ARCHIVE_DAYS)
    print('days present: %d  (%s .. %s)'
          % (len(meta_days), meta_days[0] if meta_days else '-',
             meta_days[-1] if meta_days else '-'))

    if len(meta_days) <= ARCHIVE_DAYS:
        print('\nInside the window already. Nothing to prune.')
        return 0

    keep = set(meta_days[-ARCHIVE_DAYS:])
    cutoff = min(keep)
    print('keeping     : %s and newer' % cutoff)

    every = day_dirs()
    doomed = [p for p in every if os.path.basename(p) < cutoff]

    print('day folders : %d total, %d older than the cutoff' % (len(every), len(doomed)))

    if not doomed:
        print('\nNothing to prune.')
        return 0

    share = len(doomed) / float(len(every))
    if share > MAX_SHARE_DELETED:
        print('\nREFUSING: this would delete %.0f%% of the day folders (%d of %d).'
              % (100 * share, len(doomed), len(every)))
        print('That is not a steady-state prune. Check the dates before forcing it.')
        return 1

    print()
    freed = 0
    for p in doomed:
        n = size_of(p)
        freed += n
        print('  %-52s %8.1f KB' % (os.path.relpath(p, ROOT), n / 1024.0))
        if apply:
            shutil.rmtree(p)

    print()
    print('%s %d folders, %.1f MB'
          % ('removed' if apply else 'would remove', len(doomed), freed / 1048576.0))
    if not apply:
        print('\nDry run. Re-run with --apply to delete.')
    else:
        r = refresh_pointer()
        if r:
            print('pointer     : day_count %s -> %d, snapshot_count %d'
                  % (r[0], r[1], r[2]))
        print()
        print('The full archive lives in the private mirror. This only bounds')
        print('the working tree of the public repository; git history is unchanged.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
