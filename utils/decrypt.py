import sys
import json
import argparse
from pathlib import Path

from utils.encryption import DataEncryption

# Decrypt encrypted backup file
def decrypt_file(input_path: str, output_path: str = None, encryption_key: str = None):
    input_file = Path(input_path)

    if not input_file.exists():
        print(f"❌ File not found: {input_path}")
        sys.exit(1)

    # Initialize decryptor with custom key or from .env
    if encryption_key:
        decryptor = DataEncryption(password=encryption_key)
    else:
        decryptor = DataEncryption()

    # Read and decrypt file
    try:
        with open(input_file, 'rb') as f:
            encrypted_data = f.read()

        data = decryptor.decrypt_json(encrypted_data)

        # Save to file or display in terminal
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Decrypted file saved: {output_path}")
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))

        return data

    except Exception as e:
        print(f"❌ Decryption error: {e}")
        print("⚠️  Check that ENCRYPTION_KEY is correct in your .env")
        sys.exit(1)

# CLI entry point
def main():
    parser = argparse.ArgumentParser(
        description='Decrypt CozyBot .enc backup files'
    )
    parser.add_argument(
        'input',
        help='.enc file to decrypt'
    )
    parser.add_argument(
        '-o', '--output',
        help='JSON output file (optional, displays in terminal otherwise)'
    )
    parser.add_argument(
        '-k', '--key',
        help='Encryption key (optional, uses ENCRYPTION_KEY from .env otherwise)'
    )

    args = parser.parse_args()
    decrypt_file(args.input, args.output, args.key)

if __name__ == '__main__':
    main()
