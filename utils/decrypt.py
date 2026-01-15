import sys
import json
import argparse
from pathlib import Path

# Import du système de chiffrement du bot
from utils.encryption import DataEncryption

def decrypt_file(input_path: str, output_path: str = None, encryption_key: str = None):
    """Déchiffre un fichier .enc et l'affiche ou le sauvegarde en JSON"""
    input_file = Path(input_path)

    if not input_file.exists():
        print(f"❌ Fichier introuvable: {input_path}")
        sys.exit(1)

    # Initialiser le déchiffreur
    if encryption_key:
        decryptor = DataEncryption(password=encryption_key)
    else:
        # Utilise ENCRYPTION_KEY de .env
        decryptor = DataEncryption()

    try:
        # Lire le fichier chiffré
        with open(input_file, 'rb') as f:
            encrypted_data = f.read()

        # Déchiffrer
        data = decryptor.decrypt_json(encrypted_data)

        if output_path:
            # Sauvegarder en JSON
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Fichier déchiffré sauvegardé: {output_path}")
        else:
            # Afficher dans le terminal
            print(json.dumps(data, indent=2, ensure_ascii=False))

        return data

    except Exception as e:
        print(f"❌ Erreur lors du déchiffrement: {e}")
        print("⚠️  Vérifie que ENCRYPTION_KEY est correcte dans ton .env")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description='Déchiffre les fichiers .enc des backups CozyBot'
    )
    parser.add_argument(
        'input',
        help='Fichier .enc à déchiffrer'
    )
    parser.add_argument(
        '-o', '--output',
        help='Fichier JSON de sortie (optionnel, affiche dans le terminal sinon)'
    )
    parser.add_argument(
        '-k', '--key',
        help='Clé de chiffrement (optionnel, utilise ENCRYPTION_KEY de .env sinon)'
    )

    args = parser.parse_args()
    decrypt_file(args.input, args.output, args.key)

if __name__ == '__main__':
    main()
