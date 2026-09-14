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
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'raw')

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
        print('\nThe full archive lives in the private mirror. This only bounds')
        print('the working tree of the public repository; git history is unchanged.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
