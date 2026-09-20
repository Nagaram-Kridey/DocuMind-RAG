#!/usr/bin/env sh
# Fetch the exact Django documentation revision used by DocuMind.

set -eu

DJANGO_TAG="5.2.9"
DJANGO_COMMIT="c14b756185c88f7f2eb745ff061f3c221fea9de7"
REPOSITORY_URL="https://github.com/django/django.git"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
TARGET_DIR="$REPOSITORY_ROOT/data/django-5.2"

if ! command -v git >/dev/null 2>&1; then
    echo "git is required to fetch the Django documentation." >&2
    exit 1
fi

if [ -e "$TARGET_DIR" ]; then
    if [ ! -d "$TARGET_DIR/.git" ]; then
        echo "Corpus path exists but is not a Git checkout: $TARGET_DIR" >&2
        exit 1
    fi

    CURRENT_COMMIT=$(git -C "$TARGET_DIR" rev-parse HEAD)
    if [ "$CURRENT_COMMIT" = "$DJANGO_COMMIT" ]; then
        echo "Django documentation is already pinned at $DJANGO_TAG ($DJANGO_COMMIT)."
        exit 0
    fi

    echo "Corpus checkout has an unexpected revision: $CURRENT_COMMIT" >&2
    exit 1
fi

mkdir -p "$(dirname -- "$TARGET_DIR")"
git clone --depth 1 --branch "$DJANGO_TAG" --filter=blob:none --sparse "$REPOSITORY_URL" "$TARGET_DIR"
git -C "$TARGET_DIR" sparse-checkout set docs

ACTUAL_COMMIT=$(git -C "$TARGET_DIR" rev-parse HEAD)
if [ "$ACTUAL_COMMIT" != "$DJANGO_COMMIT" ]; then
    echo "Expected $DJANGO_COMMIT but fetched $ACTUAL_COMMIT." >&2
    exit 1
fi

echo "Fetched Django documentation $DJANGO_TAG at $ACTUAL_COMMIT."
