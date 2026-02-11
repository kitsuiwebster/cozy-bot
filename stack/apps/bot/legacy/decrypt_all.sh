#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_directory>"
    echo "Example: $0 ~/backups/2026-01-15/prod"
    exit 1
fi

BACKUP_DIR="$1"
OUTPUT_DIR="${BACKUP_DIR}/decrypted"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Directory not found: $BACKUP_DIR"
    exit 1
fi

echo "📂 Decrypting from: $BACKUP_DIR"
mkdir -p "$OUTPUT_DIR"

# Decrypt all .enc files
for enc_file in "$BACKUP_DIR"/*.enc; do
    if [ -f "$enc_file" ]; then
        filename=$(basename "$enc_file" .enc)
        output_file="$OUTPUT_DIR/${filename}.json"

        echo "🔓 Decrypting: $filename.enc → ${filename}.json"
        python3 "$(dirname "$0")/decrypt.py" "$enc_file" -o "$output_file"
    fi
done

echo "✅ Decryption completed in: $OUTPUT_DIR"
