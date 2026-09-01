# Duplicate File Finder

I built this because my own downloads folder is a mess of the same file
saved three times under different names. This script walks a directory,
finds files that are exact duplicates (same content, byte for byte), and
tells you how much space you'd get back if you cleaned them up.

## How to run it

python dedupe.py /path/to/folder

Optional flags:
python dedupe.py /path/to/folder --min-size 1024   # skip tiny files
python dedupe.py /path/to/folder --delete           # remove the extra copies (asks before deleting anything)

## How it actually works

Comparing every file to every other file by content would be slow, so I
do it in two passes. First I group files by size — if two files are
different sizes, they obviously can't be identical, so there's no point
hashing them. Only once a size has more than one file in it do I bother
computing a SHA-256 hash and comparing those.

I also read files in chunks instead of loading them whole into memory,
since I didn't want this to choke on a large video file. Symlinks get
skipped so it doesn't loop or double-count, and I ignore junk folders
like .git, node_modules, and venv since those aren't "your files" in any
meaningful sense.

## What was annoying, and what I'd do differently

Getting the size-then-hash logic right took a couple of tries — my first
version just hashed everything, which works but is needlessly slow on a
big folder. Realizing most files have unique sizes and can be ruled out
for free was the actual improvement.

If I had more time I'd add multiprocessing, since hashing is the
bottleneck and it's an embarrassingly parallel problem. I also don't
handle hardlinks specially right now — two hardlinks to the same file on
disk get reported as duplicates even though they're already sharing the
same storage, which is technically wrong.
