#!/usr/bin/env python3
"""
JSON data migration script to CouchDB
Migrates data from stack/data/ to CouchDB
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

# Load environment variables from stack/infra/.env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / 'stack' / 'infra' / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Environment variables loaded from {env_path}")
except ImportError:
    print("⚠️  python-dotenv not installed, using system environment variables")

# CouchDB configuration from environment variables
COUCHDB_PORT = os.getenv('COUCHDB_PORT', '5984')
COUCHDB_USER = os.getenv('COUCHDB_USER', 'admin')
COUCHDB_PASSWORD = os.getenv('COUCHDB_PASSWORD')

# For migration script, always use localhost with exposed port
COUCHDB_HOST = 'localhost'
COUCHDB_URL = f"http://{COUCHDB_HOST}:{COUCHDB_PORT}"

# Single database for all data
DATABASE_NAME = 'cozy_bot_data'

# JSON file names
FILE_COZY_POINTS = 'cozy_points.json'
FILE_USERNAMES = 'usernames.json'
FILE_SERVERNAMES = 'servernames.json'
FILE_CURRENT_STATS = 'current_stats.json'
FILE_VOICE_TIME = 'voice_time_data.json'
FILE_DEPLOYMENT = 'deployment_notification.json'

# Mapping of JSON files to ID prefixes and document types
DOC_TYPE_MAPPING = {
    FILE_COZY_POINTS: {
        'prefix': 'user:',
        'type': 'user'
    },
    FILE_USERNAMES: {
        'prefix': 'username:',
        'type': 'username'
    },
    FILE_SERVERNAMES: {
        'prefix': 'server:',
        'type': 'server'
    },
    FILE_CURRENT_STATS: {
        'prefix': 'stats:',
        'type': 'stats'
    },
    FILE_VOICE_TIME: {
        'prefix': 'voice_time:',
        'type': 'voice_time'
    },
    FILE_DEPLOYMENT: {
        'prefix': 'deployment:',
        'type': 'deployment'
    }
}


class CouchDBMigrator:
    def __init__(self):
        if not COUCHDB_PASSWORD:
            print("❌ COUCHDB_PASSWORD not defined in environment")
            sys.exit(1)

        # Create HTTP Basic authentication header
        credentials = f"{COUCHDB_USER}:{COUCHDB_PASSWORD}"
        self.auth_header = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            'Authorization': f'Basic {self.auth_header}',
            'Content-Type': 'application/json'
        }

    def check_connection(self) -> bool:
        """Check connection to CouchDB"""
        try:
            req = urllib.request.Request(COUCHDB_URL, headers=self.headers)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                print(f"✅ CouchDB connection successful: {data.get('couchdb', 'unknown')} version {data.get('version', 'unknown')}")
                return True
        except urllib.error.HTTPError as e:
            print(f"❌ CouchDB connection error: {e.code}")
            return False
        except Exception as e:
            print(f"❌ Unable to connect to CouchDB: {e}")
            return False

    def create_database(self, db_name: str) -> bool:
        """Create database if it doesn't exist"""
        try:
            # Check if database exists
            req = urllib.request.Request(f"{COUCHDB_URL}/{db_name}", headers=self.headers, method='HEAD')
            try:
                urllib.request.urlopen(req)
                print(f"ℹ️  Database '{db_name}' already exists")
                return True
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise

            # Create database
            req = urllib.request.Request(f"{COUCHDB_URL}/{db_name}", headers=self.headers, method='PUT')
            with urllib.request.urlopen(req) as response:
                if response.status in [201, 202]:
                    print(f"✅ Database '{db_name}' created")
                    return True
                else:
                    print(f"❌ Database creation error '{db_name}': {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error creating '{db_name}': {e}")
            return False

    def migrate_file(self, file_path: Path, doc_config: dict) -> bool:
        """Migrate JSON file to single CouchDB database"""
        try:
            prefix = doc_config['prefix']
            doc_type = doc_config['type']

            print(f"\n📁 Migrating {file_path.name} (type: {doc_type})...")

            # Read JSON file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Determine data format
            if isinstance(data, dict):
                # For files like cozy_points.json, usernames.json, servernames.json
                # where each key is a numeric ID
                return self._migrate_dict_data(data, prefix, doc_type, file_path.name)
            elif isinstance(data, list):
                # For list-type files
                return self._migrate_list_data(data, prefix, doc_type)
            else:
                print(f"⚠️  Unrecognized data format for {file_path.name}")
                return False

        except Exception as e:
            print(f"❌ Migration error {file_path.name}: {e}")
            return False

    def _create_single_doc(self, data: Dict, prefix: str, doc_type: str, filename: str) -> Dict:
        """Create a single document for special files"""
        doc = data.copy()
        doc['type'] = doc_type

        if filename == FILE_CURRENT_STATS:
            doc['_id'] = f"{prefix}current"
        elif filename == FILE_DEPLOYMENT:
            doc['_id'] = f"{prefix}{data.get('timestamp', 'latest')}"

        return doc

    def _insert_document(self, doc: Dict) -> None:
        """Insert a document into CouchDB. Raises exception on error (except 409)."""
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
                return
        except urllib.error.HTTPError as e:
            if e.code == 409:
                return
            raise

    def _migrate_single_document(self, data: Dict, prefix: str, doc_type: str, filename: str) -> bool:
        """Migrate a file containing a single document"""
        doc = self._create_single_doc(data, prefix, doc_type, filename)

        try:
            self._insert_document(doc)
            print(f"✅ Document '{doc['_id']}' inserted")
            return True
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode()
            print(f"❌ Insert error '{doc['_id']}': {e.code} - {error_msg}")
            return False

    def _create_item_doc(self, item_id: str, item_data: Any, prefix: str, doc_type: str) -> Dict:
        """Create a CouchDB document from an item"""
        doc = item_data.copy() if isinstance(item_data, dict) else {'data': item_data}
        doc['_id'] = f"{prefix}{item_id}"
        doc['type'] = doc_type
        return doc

    def _insert_item(self, doc: Dict) -> bool:
        """Insert an item and return True if successful, False otherwise"""
        try:
            self._insert_document(doc)
            return True
        except Exception:
            return False

    def _migrate_multiple_documents(self, data: Dict, prefix: str, doc_type: str) -> bool:
        """Migrate a file containing multiple documents"""
        total = len(data)
        success = 0
        failed = 0
        shown_success = 0
        shown_errors = 0

        for item_id, item_data in data.items():
            doc = self._create_item_doc(item_id, item_data, prefix, doc_type)
            is_success = self._insert_item(doc)

            if is_success:
                success += 1
                if shown_success < 3:
                    print(f"  ✓ {doc['_id']}")
                    shown_success += 1
            else:
                failed += 1
                if shown_errors < 3:
                    print(f"⚠️  Error for {item_id}")
                    shown_errors += 1

        print(f"✅ {success}/{total} documents inserted ({failed} errors)")
        return failed == 0

    def _migrate_dict_data(self, data: Dict, prefix: str, doc_type: str, filename: str) -> bool:
        """Migrate dictionary-type data"""
        if filename in [FILE_CURRENT_STATS, FILE_DEPLOYMENT]:
            return self._migrate_single_document(data, prefix, doc_type, filename)

        return self._migrate_multiple_documents(data, prefix, doc_type)

    def _migrate_list_data(self, data: list, prefix: str, doc_type: str) -> bool:
        """Migrate list-type data"""
        doc = {
            '_id': f"{prefix}all",
            'data': data,
            'type': doc_type
        }

        try:
            self._insert_document(doc)
            print(f"✅ Document '{doc['_id']}' inserted ({len(data)} items)")
            return True
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode()
            print(f"❌ Insert error: {e.code} - {error_msg}")
            return False


def create_views(migrator: CouchDBMigrator) -> bool:
    """Create CouchDB views to organize documents in Fauxton"""
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

        with urllib.request.urlopen(req):
            print("✅ CouchDB views created")
            return True
    except urllib.error.HTTPError as e:
        if e.code == 409:
            print("ℹ️  Views already exist")
            return True
        print(f"❌ View creation error: {e.code} - {e.read().decode()}")
        return False
    except Exception as e:
        print(f"❌ View creation error: {e}")
        return False


def main():
    """Main entry point"""
    print("🚀 Starting migration to CouchDB\n")

    # Path to JSON files (absolute)
    workspace_dir = Path(__file__).parent.parent
    json_dir = workspace_dir / 'stack' / 'data'

    if not json_dir.exists():
        print(f"❌ Directory not found: {json_dir}")
        print(f"ℹ️  Workspace directory: {workspace_dir}")
        print(f"ℹ️  Script path: {Path(__file__)}")
        sys.exit(1)

    print(f"📂 Source directory: {json_dir}\n")

    # Initialize migrator
    migrator = CouchDBMigrator()

    # Check connection
    if not migrator.check_connection():
        sys.exit(1)

    print("\n📊 Configuration:")
    print(f"   - Host: {COUCHDB_HOST}:{COUCHDB_PORT}")
    print(f"   - User: {COUCHDB_USER}")
    print(f"   - URL: {COUCHDB_URL}")
    print(f"   - Database: {DATABASE_NAME}")

    # Create single database
    print("\n🗄️  Creating database...")
    if not migrator.create_database(DATABASE_NAME):
        sys.exit(1)

    # Migrate each file
    all_success = True
    total_docs = 0

    for json_file, doc_config in DOC_TYPE_MAPPING.items():
        file_path = json_dir / json_file

        if not file_path.exists():
            print(f"⚠️  File not found: {json_file}")
            continue

        success = migrator.migrate_file(file_path, doc_config)
        if not success:
            all_success = False

        # Count documents
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    total_docs += len(data) if json_file != FILE_CURRENT_STATS else 1
                elif isinstance(data, list):
                    total_docs += 1
        except Exception:
            pass

    # Create CouchDB views
    print("\n📊 Creating CouchDB views...")
    create_views(migrator)

    # Final summary
    print("\n" + "="*60)
    if all_success:
        print("✅ Migration completed successfully!")
    else:
        print("⚠️  Migration completed with errors")
    print("="*60)

    # Display created database
    print(f"\n📊 CouchDB database: {DATABASE_NAME}")
    print(f"   Total documents: ~{total_docs}")
    print("\n📝 Document types:")
    for json_file, config in DOC_TYPE_MAPPING.items():
        print(f"   - {config['type']} (prefix: {config['prefix']})")

    print(f"\n🌐 CouchDB Fauxton Interface: http://{COUCHDB_HOST}:{COUCHDB_PORT}/_utils")
    print(f"   → Access: {DATABASE_NAME}")


if __name__ == '__main__':
    main()
