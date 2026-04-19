#!/usr/bin/env python3
"""
organize-downloads.py — Sort ~/Downloads into Google Drive folders.

Usage:
  python3 organize-downloads.py          # dry-run (prints what would move)
  python3 organize-downloads.py --move   # actually move files
  python3 organize-downloads.py --auto   # same as --move (for cron)

Destination: ~/Library/CloudStorage/GoogleDrive-<your-account>/My Drive/
"""
import os, sys, shutil, glob

DOWNLOADS = os.path.expanduser("~/Downloads")
CREDENTIALS = os.path.expanduser("~/.openclaw/credentials")

def find_gdrive():
    """Auto-detect Google Drive path for any Google account."""
    cloud = os.path.expanduser("~/Library/CloudStorage")
    if os.path.isdir(cloud):
        for entry in os.listdir(cloud):
            if entry.startswith("GoogleDrive-"):
                candidate = os.path.join(cloud, entry, "My Drive")
                if os.path.isdir(candidate):
                    return candidate
    legacy = os.path.expanduser("~/Google Drive/My Drive")
    if os.path.isdir(legacy):
        return legacy
    raise RuntimeError("Google Drive not found. Is Google Drive for Desktop installed?")

GDRIVE = find_gdrive()

# Never touch these dirs/files inside Downloads
SKIP = {"Google Drive", "Videos", ".DS_Store"}

# Category rules: (destination_subdir, match_function)
def categorize(name, path):
    lower = name.lower()
    ext = lower.rsplit(".", 1)[-1] if "." in lower else ""

    # Credentials — move out of Drive entirely
    if "client_secret" in lower or lower.endswith(".json") and "secret" in lower:
        return CREDENTIALS, "Credentials"

    # Screenshots (Android/phone naming pattern or macOS)
    if name.startswith("Screenshot_") or name.startswith("Screen Shot"):
        return os.path.join(GDRIVE, "Screenshots"), "Screenshots"

    # Gemini / AI-generated images
    if name.startswith("Gemini_Generated") or name.startswith("AI_Generated"):
        return os.path.join(GDRIVE, "AI Generated Images"), "AI Generated Images"

    # Images (generic)
    if ext in ("jpg", "jpeg", "png", "heic", "gif", "webp", "bmp", "tiff"):
        # Numbered filenames = phone exports
        base = name.rsplit(".", 1)[0]
        if base.lstrip("-").isdigit() or base.startswith("IMG_") or base.startswith("DCIM"):
            return os.path.join(GDRIVE, "Photos"), "Photos"
        return os.path.join(GDRIVE, "Photos"), "Photos"

    # Software installers
    if ext in ("pkg", "dmg", "exe", "msi", "deb", "rpm", "appimage"):
        return os.path.join(GDRIVE, "Software"), "Software"

    # Documents
    if ext in ("pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", "md"):
        return os.path.join(GDRIVE, "Documents"), "Documents"

    # Videos
    if ext in ("mp4", "mov", "mkv", "avi", "webm", "m4v"):
        return os.path.join(GDRIVE, "Videos"), "Videos"

    # Audio
    if ext in ("mp3", "m4a", "wav", "flac", "aac"):
        return os.path.join(GDRIVE, "Audio"), "Audio"

    return None, None  # skip — no match


def main():
    dry_run = "--move" not in sys.argv and "--auto" not in sys.argv
    if dry_run:
        print("DRY RUN — pass --move to actually move files\n")

    moves = []
    skipped = []

    for name in os.listdir(DOWNLOADS):
        if name in SKIP or name.startswith("."):
            continue
        src = os.path.join(DOWNLOADS, name)
        dest_dir, label = categorize(name, src)
        if dest_dir is None:
            skipped.append(name)
            continue
        dest = os.path.join(dest_dir, name)
        moves.append((src, dest, label, name))

    if not moves:
        print("Nothing to organize.")
        return

    # Print manifest
    by_label = {}
    for src, dest, label, name in moves:
        by_label.setdefault(label, []).append(name)

    print(f"{'Would move' if dry_run else 'Moving'} {len(moves)} item(s):\n")
    for label, names in sorted(by_label.items()):
        print(f"  [{label}]")
        for n in names:
            print(f"    {n}")

    if dry_run:
        print(f"\nSkipped (no category): {skipped if skipped else 'none'}")
        print("\nRun with --move to apply.")
        return

    # Execute moves
    errors = []
    for src, dest, label, name in moves:
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            # Handle name collision
            if os.path.exists(dest):
                base, ext = os.path.splitext(name)
                import time
                dest = os.path.join(os.path.dirname(dest), f"{base}_{int(time.time())}{ext}")
            shutil.move(src, dest)
            print(f"  Moved: {name} → {os.path.dirname(dest).replace(os.path.expanduser('~'), '~')}/")
        except Exception as e:
            errors.append(f"  ERROR {name}: {e}")

    if errors:
        print("\nErrors:")
        for e in errors:
            print(e)
    else:
        print(f"\nDone. {len(moves)} file(s) organized.")

    if skipped:
        print(f"Skipped (no category): {skipped}")


if __name__ == "__main__":
    main()
