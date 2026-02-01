#!/usr/bin/env python3
"""
Script de migration des données JSON vers CouchDB
Migre les données depuis stack/data/ vers CouchDB
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
import base64
from pathlib import Path
from typing import Dict, Any

# Charger les variables d'environnement depuis stack/infra/.env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / 'stack' / 'infra' / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Variables d'environnement chargées depuis {env_path}")
except ImportError:
    print("⚠️  python-dotenv non installé, utilisation des variables d'environnement système")

# Configuration CouchDB depuis variables d'environnement
COUCHDB_PORT = os.getenv('COUCHDB_PORT', '5984')
COUCHDB_USER = os.getenv('COUCHDB_USER', 'admin')
COUCHDB_PASSWORD = os.getenv('COUCHDB_PASSWORD')

# Pour le script de migration, on utilise toujours localhost avec le port exposé
COUCHDB_HOST = 'localhost'
COUCHDB_URL = f"http://{COUCHDB_HOST}:{COUCHDB_PORT}"

# Base de données unique pour toutes les données
DATABASE_NAME = 'cozy_bot_data'

# Mapping des fichiers JSON vers les préfixes d'ID et types de documents
DOC_TYPE_MAPPING = {
    'cozy_points.json': {
        'prefix': 'user:',
        'type': 'user'
    },
    'usernames.json': {
        'prefix': 'username:',
        'type': 'username'
    },
    'servernames.json': {
        'prefix': 'server:',
        'type': 'server'
    },
    'current_stats.json': {
        'prefix': 'stats:',
        'type': 'stats'
    },
    'voice_time_data.json': {
        'prefix': 'voice_time:',
        'type': 'voice_time'
    },
    'deployment_notification.json': {
        'prefix': 'deployment:',
        'type': 'deployment'
    }
}


class CouchDBMigrator:
    def __init__(self):
        if not COUCHDB_PASSWORD:
            print("❌ COUCHDB_PASSWORD non défini dans l'environnement")
            sys.exit(1)

        # Créer l'en-tête d'authentification HTTP Basic
        credentials = f"{COUCHDB_USER}:{COUCHDB_PASSWORD}"
        self.auth_header = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            'Authorization': f'Basic {self.auth_header}',
            'Content-Type': 'application/json'
        }

    def check_connection(self) -> bool:
        """Vérifie la connexion à CouchDB"""
        try:
            req = urllib.request.Request(COUCHDB_URL, headers=self.headers)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                print(f"✅ Connexion CouchDB réussie: {data.get('couchdb', 'unknown')} version {data.get('version', 'unknown')}")
                return True
        except urllib.error.HTTPError as e:
            print(f"❌ Erreur de connexion CouchDB: {e.code}")
            return False
        except Exception as e:
            print(f"❌ Impossible de se connecter à CouchDB: {e}")
            return False

    def create_database(self, db_name: str) -> bool:
        """Crée une base de données si elle n'existe pas"""
        try:
            # Vérifier si la base existe
            req = urllib.request.Request(f"{COUCHDB_URL}/{db_name}", headers=self.headers, method='HEAD')
            try:
                urllib.request.urlopen(req)
                print(f"ℹ️  Base de données '{db_name}' existe déjà")
                return True
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise

            # Créer la base
            req = urllib.request.Request(f"{COUCHDB_URL}/{db_name}", headers=self.headers, method='PUT')
            with urllib.request.urlopen(req) as response:
                if response.status in [201, 202]:
                    print(f"✅ Base de données '{db_name}' créée")
                    return True
                else:
                    print(f"❌ Erreur création base '{db_name}': {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Erreur lors de la création de '{db_name}': {e}")
            return False

    def migrate_file(self, file_path: Path, doc_config: dict) -> bool:
        """Migre un fichier JSON vers la base CouchDB unique"""
        try:
            prefix = doc_config['prefix']
            doc_type = doc_config['type']

            print(f"\n📁 Migration de {file_path.name} (type: {doc_type})...")

            # Lire le fichier JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Déterminer le format des données
            if isinstance(data, dict):
                # Pour les fichiers comme cozy_points.json, usernames.json, servernames.json
                # où chaque clé est un ID numérique
                return self._migrate_dict_data(data, prefix, doc_type, file_path.name)
            elif isinstance(data, list):
                # Pour les fichiers de type liste
                return self._migrate_list_data(data, prefix, doc_type, file_path.name)
            else:
                print(f"⚠️  Format de données non reconnu pour {file_path.name}")
                return False

        except Exception as e:
            print(f"❌ Erreur migration {file_path.name}: {e}")
            return False

    def _migrate_dict_data(self, data: Dict, prefix: str, doc_type: str, filename: str) -> bool:
        """Migre des données de type dictionnaire"""
        total = len(data)
        success = 0
        failed = 0

        # Cas spéciaux pour les fichiers avec un seul document JSON (pas de dictionnaire d'IDs)
        if filename in ['current_stats.json', 'deployment_notification.json']:
            # ID différent selon le fichier
            if filename == 'current_stats.json':
                doc = data.copy()
                doc['_id'] = f"{prefix}current"
                doc['type'] = doc_type
            elif filename == 'deployment_notification.json':
                doc = data.copy()
                # Utiliser le timestamp comme ID pour garder l'historique des déploiements
                doc['_id'] = f"{prefix}{data.get('timestamp', 'latest')}"
                doc['type'] = doc_type

            doc_json = json.dumps(doc).encode('utf-8')
            encoded_id = urllib.parse.quote(doc['_id'], safe='')
            req = urllib.request.Request(
                f"{COUCHDB_URL}/{DATABASE_NAME}/{encoded_id}",
                data=doc_json,
                headers=self.headers,
                method='PUT'
            )

            try:
                with urllib.request.urlopen(req) as response:
                    print(f"✅ Document '{doc['_id']}' inséré")
                    return True
            except urllib.error.HTTPError as e:
                error_msg = e.read().decode() if e.code != 409 else "Document exists (409)"
                if e.code == 409:
                    print(f"ℹ️  Document '{doc['_id']}' existe déjà (ignoré)")
                    return True
                print(f"❌ Erreur insertion '{doc['_id']}': {e.code} - {error_msg}")
                return False

        # Pour les autres fichiers (dictionnaires avec des IDs)
        for item_id, item_data in data.items():
            try:
                # Créer le document CouchDB
                doc = item_data.copy() if isinstance(item_data, dict) else {'data': item_data}

                # Utiliser l'ID numérique directement (discord_id ou guild_id)
                doc['_id'] = f"{prefix}{item_id}"
                doc['type'] = doc_type

                # Insérer le document
                doc_json = json.dumps(doc).encode('utf-8')
                # Encoder l'ID pour les URLs (gère les caractères spéciaux)
                encoded_id = urllib.parse.quote(doc['_id'], safe='')
                req = urllib.request.Request(
                    f"{COUCHDB_URL}/{DATABASE_NAME}/{encoded_id}",
                    data=doc_json,
                    headers=self.headers,
                    method='PUT'
                )

                try:
                    with urllib.request.urlopen(req):
                        success += 1
                        if success <= 3:  # Afficher quelques exemples
                            print(f"  ✓ {doc['_id']}")
                except urllib.error.HTTPError as e:
                    if e.code == 409:
                        # Document existe déjà, on ignore silencieusement
                        success += 1
                    else:
                        failed += 1
                        if failed <= 3:  # Afficher quelques erreurs
                            print(f"⚠️  Erreur pour {item_id}: {e.code}")

            except Exception as e:
                failed += 1
                if failed <= 3:
                    print(f"⚠️  Erreur pour {item_id}: {e}")

        print(f"✅ {success}/{total} documents insérés ({failed} erreurs)")
        return failed == 0

    def _migrate_list_data(self, data: list, prefix: str, doc_type: str, filename: str) -> bool:
        """Migre des données de type liste"""
        # Insérer la liste complète comme un seul document
        doc = {
            '_id': f"{prefix}all",
            'data': data,
            'type': doc_type
        }

        doc_json = json.dumps(doc).encode('utf-8')
        encoded_id = urllib.parse.quote(doc['_id'], safe='')
        req = urllib.request.Request(
            f"{COUCHDB_URL}/{DATABASE_NAME}/{encoded_id}",
            data=doc_json,
            headers=self.headers,
            method='PUT'
        )

        try:
            with urllib.request.urlopen(req):
                print(f"✅ Document '{doc['_id']}' inséré ({len(data)} items)")
                return True
        except urllib.error.HTTPError as e:
            if e.code == 409:
                print(f"ℹ️  Document '{doc['_id']}' existe déjà (ignoré)")
                return True
            print(f"❌ Erreur insertion: {e.code} - {e.read().decode()}")
            return False


def create_views(migrator: CouchDBMigrator) -> bool:
    """Crée les vues CouchDB pour organiser les documents dans Fauxton"""
    design_doc = {
        "_id": "_design/views",
        "views": {
            "users": {
                "map": "function(doc) { if(doc.type === 'user') { emit(doc._id, {total_points: doc.total_points, level: doc.level, listening_time: doc.listening_time}); } }"
            },
            "usernames": {
                "map": "function(doc) { if(doc.type === 'username') { emit(doc._id, {username: doc.username, display_name: doc.display_name}); } }"
            },
            "servers": {
                "map": "function(doc) { if(doc.type === 'server') { emit(doc._id, {name: doc.name, last_updated: doc.last_updated}); } }"
            },
            "voice_time": {
                "map": "function(doc) { if(doc.type === 'voice_time') { var guild_id = doc._id.replace('voice_time:', ''); emit(guild_id, doc.data); } }"
            },
            "all_by_type": {
                "map": "function(doc) { if(doc.type) { emit(doc.type, doc._id); } }"
            },
            "deployments": {
                "map": "function(doc) { if(doc.type === 'deployment') { emit(doc._id, {version: doc.version, timestamp: doc.timestamp, status: doc.status}); } }"
            }
        }
    }

    try:
        doc_json = json.dumps(design_doc).encode('utf-8')
        req = urllib.request.Request(
            f"{COUCHDB_URL}/{DATABASE_NAME}/_design/views",
            data=doc_json,
            headers=migrator.headers,
            method='PUT'
        )

        with urllib.request.urlopen(req) as response:
            print("✅ Vues CouchDB créées")
            return True
    except urllib.error.HTTPError as e:
        if e.code == 409:
            print("ℹ️  Vues existent déjà")
            return True
        print(f"❌ Erreur création des vues: {e.code} - {e.read().decode()}")
        return False
    except Exception as e:
        print(f"❌ Erreur création des vues: {e}")
        return False


def main():
    """Point d'entrée principal"""
    print("🚀 Démarrage de la migration vers CouchDB\n")

    # Chemin vers les fichiers JSON (absolu)
    workspace_dir = Path(__file__).parent.parent
    json_dir = workspace_dir / 'stack' / 'data'

    if not json_dir.exists():
        print(f"❌ Répertoire non trouvé: {json_dir}")
        print(f"ℹ️  Répertoire workspace: {workspace_dir}")
        print(f"ℹ️  Script path: {Path(__file__)}")
        sys.exit(1)

    print(f"📂 Répertoire source: {json_dir}\n")

    # Initialiser le migrateur
    migrator = CouchDBMigrator()

    # Vérifier la connexion
    if not migrator.check_connection():
        sys.exit(1)

    print(f"\n📊 Configuration:")
    print(f"   - Host: {COUCHDB_HOST}:{COUCHDB_PORT}")
    print(f"   - User: {COUCHDB_USER}")
    print(f"   - URL: {COUCHDB_URL}")
    print(f"   - Database: {DATABASE_NAME}")

    # Créer la base de données unique
    print(f"\n🗄️  Création de la base de données...")
    if not migrator.create_database(DATABASE_NAME):
        sys.exit(1)

    # Migrer chaque fichier
    all_success = True
    total_docs = 0

    for json_file, doc_config in DOC_TYPE_MAPPING.items():
        file_path = json_dir / json_file

        if not file_path.exists():
            print(f"⚠️  Fichier non trouvé: {json_file}")
            continue

        success = migrator.migrate_file(file_path, doc_config)
        if not success:
            all_success = False

        # Compter les documents
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    total_docs += len(data) if json_file != 'current_stats.json' else 1
                elif isinstance(data, list):
                    total_docs += 1
        except:
            pass

    # Créer les vues CouchDB
    print(f"\n📊 Création des vues CouchDB...")
    create_views(migrator)

    # Résumé final
    print("\n" + "="*60)
    if all_success:
        print("✅ Migration terminée avec succès!")
    else:
        print("⚠️  Migration terminée avec des erreurs")
    print("="*60)

    # Afficher la base créée
    print(f"\n📊 Base de données CouchDB: {DATABASE_NAME}")
    print(f"   Total documents: ~{total_docs}")
    print(f"\n📝 Types de documents:")
    for json_file, config in DOC_TYPE_MAPPING.items():
        print(f"   - {config['type']} (préfixe: {config['prefix']})")

    print(f"\n🌐 Interface CouchDB Fauxton: http://{COUCHDB_HOST}:{COUCHDB_PORT}/_utils")
    print(f"   → Accéder à: {DATABASE_NAME}")


if __name__ == '__main__':
    main()
