import couchdb3
import logging
import os
import urllib.request
import json
import threading
import queue
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import urllib.parse

class CouchDBClient:
    """
    CouchDB client wrapper for managing bot data storage.
    Replaces file-based JSON storage with CouchDB.
    """

    def __init__(self):
        self.host = os.getenv('COUCHDB_HOST', 'http://couchdb:5984')
        self.user = os.getenv('COUCHDB_USER', 'admin')
        self.password = os.getenv('COUCHDB_PASSWORD')

        if not self.password:
            raise ValueError("COUCHDB_PASSWORD environment variable is required")

        try:
            # Connect to CouchDB
            self.client = couchdb3.Server(
                f"{self.host}",
                user=self.user,
                password=self.password
            )

            # Initialize databases
            self._init_databases()
            self._writer = None
            if os.getenv("COUCHDB_WRITE_WORKER", "0") == "1":
                self._writer = _CouchDBWriteWorker(self)
            logging.debug(f"✅ Connected to CouchDB at {self.host}")

        except Exception as e:
            logging.error(f"❌ Failed to connect to CouchDB: {e}")
            raise

    def _init_databases(self):
        """Initialize all required databases - using single cozy_bot_data database"""
        db_name = 'cozy_bot_data'

        try:
            if db_name not in self.client:
                self.client.create(db_name)
                logging.info(f"📁 Created database: {db_name}")
            else:
                logging.debug(f"📁 Database exists: {db_name}")
        except Exception as e:
            # Database might already exist, just log and continue
            logging.debug(f"📁 Database {db_name} already exists or error: {e}")

        # Use single database for all data
        self.db = self.client[db_name]

        # All data types use the same database with prefixed IDs:
        # - user:{discord_id} - User stats
        # - username:{discord_id} - Username cache
        # - server:{guild_id} - Server name cache
        # - voice_time:{guild_id} - Voice time tracking per server
        # - audio_state - Audio state (single doc)
        # - restore_task:{guild_id} - Restore tasks

    # Generic CRUD operations

    def get_document(self, db, doc_id: str, default: Any = None) -> Any:
        """Get a document by ID, return default if not found"""
        try:
            doc = db.get(doc_id)
            return doc if doc else default
        except Exception as e:
            logging.debug(f"Document {doc_id} not found: {e}")
            return default

    def save_document(self, db, doc_id: str, data: Dict) -> bool:
        """Save or update a document"""
        if self._writer:
            self._writer.enqueue(db, doc_id, data)
            return True
        return self._save_document_sync(db, doc_id, data)

    def _save_document_sync(self, db, doc_id: str, data: Dict) -> bool:
        """Save or update a document (sync)"""
        try:
            # Get existing document to preserve _rev
            existing = db.get(doc_id)

            if existing:
                # Update existing document
                data['_id'] = doc_id
                data['_rev'] = existing['_rev']
                data['updated_at'] = datetime.now().isoformat()
            else:
                # Create new document
                data['_id'] = doc_id
                data['created_at'] = datetime.now().isoformat()
                data['updated_at'] = datetime.now().isoformat()

            db.save(data)
            return True

        except Exception as e:
            logging.error(f"❌ Failed to save document {doc_id}: {e}")
            return False

    def delete_document(self, db, doc_id: str) -> bool:
        """Delete a document by ID"""
        try:
            doc = db.get(doc_id)
            if doc:
                rev = doc.get('_rev')
                if not rev:
                    logging.error(f"❌ Failed to delete document {doc_id}: missing _rev")
                    return False
                db.delete(doc_id, rev)
                return True
            return False
        except Exception as e:
            logging.error(f"❌ Failed to delete document {doc_id}: {e}")
            return False

    def get_all_documents(self, db) -> Dict:
        """Get all documents from a database (excluding design docs)"""
        try:
            result = {}

            # Use _all_docs view
            url = f"{self.host}/cozy_bot_data/_all_docs?include_docs=true"

            # Create auth header
            import base64
            credentials = f"{self.user}:{self.password}"
            auth_header = base64.b64encode(credentials.encode()).decode()

            headers = {
                'Authorization': f'Basic {auth_header}',
                'Content-Type': 'application/json'
            }

            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())

                for row in data.get('rows', []):
                    doc_id = row.get('id', '')
                    doc = row.get('doc', {})

                    # Skip design documents
                    if doc_id.startswith('_design/'):
                        continue

                    # Remove CouchDB metadata
                    doc_data = {k: v for k, v in doc.items()
                               if k not in ['_id', '_rev', 'created_at', 'updated_at']}

                    result[doc_id] = doc_data

            return result
        except Exception as e:
            logging.error(f"❌ Failed to get all documents: {e}")
            return {}

    def get_documents_by_prefix(self, prefix: str) -> Dict:
        """Get all documents with a specific prefix (e.g., 'user:', 'username:')"""
        try:
            result = {}

            # Use _all_docs view with startkey/endkey for prefix search
            # This is more reliable than iterating
            url = f"{self.host}/cozy_bot_data/_all_docs?include_docs=true"

            # Create auth header
            import base64
            credentials = f"{self.user}:{self.password}"
            auth_header = base64.b64encode(credentials.encode()).decode()

            headers = {
                'Authorization': f'Basic {auth_header}',
                'Content-Type': 'application/json'
            }

            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())

                for row in data.get('rows', []):
                    doc_id = row.get('id', '')
                    doc = row.get('doc', {})

                    # Skip design documents
                    if doc_id.startswith('_design/'):
                        continue

                    # Skip documents without the prefix
                    if not doc_id.startswith(prefix):
                        continue

                    # Remove prefix from doc_id for cleaner result keys
                    clean_id = doc_id[len(prefix):]

                    # Remove CouchDB metadata
                    doc_data = {k: v for k, v in doc.items()
                               if k not in ['_id', '_rev', 'created_at', 'updated_at', 'type']}

                    result[clean_id] = doc_data

            logging.debug(f"📂 Loaded {len(result)} documents with prefix '{prefix}'")
            return result
        except Exception as e:
            logging.error(f"❌ Failed to get documents by prefix '{prefix}': {e}")
            import traceback
            logging.error(f"❌ Traceback: {traceback.format_exc()}")
            return {}

    def get_documents_by_range(self, prefix: str, start_key: str, end_key: str) -> Dict:
        """Get documents by ID range (inclusive) for a given prefix"""
        try:
            result = {}

            params = {
                "include_docs": "true",
                "startkey": json.dumps(start_key),
                "endkey": json.dumps(end_key),
            }
            url = f"{self.host}/cozy_bot_data/_all_docs?{urllib.parse.urlencode(params)}"

            import base64
            credentials = f"{self.user}:{self.password}"
            auth_header = base64.b64encode(credentials.encode()).decode()

            headers = {
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/json",
            }

            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())

                for row in data.get("rows", []):
                    doc_id = row.get("id", "")
                    doc = row.get("doc", {})

                    if doc_id.startswith("_design/"):
                        continue
                    if not doc_id.startswith(prefix):
                        continue

                    doc_data = {k: v for k, v in doc.items()
                                if k not in ["_id", "_rev", "created_at", "updated_at"]}
                    result[doc_id] = doc_data

            return result
        except Exception as e:
            logging.error(f"❌ Failed to get documents by range '{prefix}': {e}")
            return {}

    # Cozy Points operations

    def load_user_data(self) -> Dict:
        """Load all user gamification data"""
        return self.get_documents_by_prefix('user:')

    def save_user_data(self, user_data: Dict) -> bool:
        """Save all user gamification data"""
        try:
            for user_id, stats in user_data.items():
                doc = stats.copy()
                doc['type'] = 'user'
                self.save_document(self.db, f'user:{user_id}', doc)
            return True
        except Exception as e:
            logging.error(f"❌ Failed to save user data: {e}")
            return False

    def get_user_stats(self, user_id: str) -> Optional[Dict]:
        """Get stats for a specific user"""
        doc = self.get_document(self.db, f'user:{user_id}')
        if doc and 'type' in doc:
            doc = {k: v for k, v in doc.items() if k != 'type'}
        return doc

    def save_user_stats(self, user_id: str, stats: Dict) -> bool:
        """Save stats for a specific user"""
        doc = stats.copy()
        doc['type'] = 'user'
        return self.save_document(self.db, f'user:{user_id}', doc)

    # Username cache operations

    def load_usernames(self) -> Dict:
        """Load username cache"""
        return self.get_documents_by_prefix('username:')

    def save_usernames(self, usernames: Dict) -> bool:
        """Save username cache"""
        try:
            for user_id, username_data in usernames.items():
                doc = username_data.copy()
                doc['type'] = 'username'
                self.save_document(self.db, f'username:{user_id}', doc)
            return True
        except Exception as e:
            logging.error(f"❌ Failed to save usernames: {e}")
            return False

    def update_username(self, user_id: str, username_data: Dict) -> bool:
        """Update a single username entry"""
        doc = username_data.copy()
        doc['type'] = 'username'
        return self.save_document(self.db, f'username:{user_id}', doc)

    # Server name cache operations

    def load_servernames(self) -> Dict:
        """Load server name cache"""
        return self.get_documents_by_prefix('server:')

    def save_servernames(self, servernames: Dict) -> bool:
        """Save server name cache"""
        try:
            for guild_id, server_data in servernames.items():
                doc = server_data.copy()
                doc['type'] = 'server'
                self.save_document(self.db, f'server:{guild_id}', doc)
            return True
        except Exception as e:
            logging.error(f"❌ Failed to save servernames: {e}")
            return False

    def update_servername(self, guild_id: str, server_data: Dict) -> bool:
        """Update a single server name entry"""
        doc = server_data.copy()
        doc['type'] = 'server'
        return self.save_document(self.db, f'server:{guild_id}', doc)

    # Voice time tracking operations

    def load_voice_time_data(self) -> Dict:
        """Load voice time tracking data"""
        docs = self.get_documents_by_prefix('voice_time:')
        # Extract 'data' field from each document
        result = {}
        for guild_id, doc in docs.items():
            result[guild_id] = doc.get('data', [None, 0])
        return result

    def save_voice_time_data(self, voice_time_data: Dict) -> bool:
        """Save voice time tracking data"""
        try:
            for guild_id, time_data in voice_time_data.items():
                doc = {'data': time_data, 'type': 'voice_time'}
                self.save_document(self.db, f'voice_time:{guild_id}', doc)
            return True
        except Exception as e:
            logging.error(f"❌ Failed to save voice time data: {e}")
            return False

    # Audio state operations

    def save_audio_state(self, state_data: Dict) -> bool:
        """Save audio restoration state"""
        doc = state_data.copy()
        doc['type'] = 'audio_state'
        return self.save_document(self.db, 'audio_state', doc)

    def load_audio_state(self) -> Optional[Dict]:
        """Load audio restoration state"""
        return self.get_document(self.db, 'audio_state')

    def delete_audio_state(self) -> bool:
        """Delete audio restoration state"""
        return self.delete_document(self.db, 'audio_state')

    # Restore task operations

    def save_restore_task(self, guild_id: str, task_data: Dict) -> bool:
        """Save a restore task for a specific guild"""
        doc = task_data.copy()
        doc['type'] = 'restore_task'
        return self.save_document(self.db, f'restore_task:{guild_id}', doc)

    def load_restore_task(self, guild_id: str) -> Optional[Dict]:
        """Load a restore task for a specific guild"""
        return self.get_document(self.db, f'restore_task:{guild_id}')

    def delete_restore_task(self, guild_id: str) -> bool:
        """Delete a restore task for a specific guild"""
        return self.delete_document(self.db, f'restore_task:{guild_id}')

    def get_all_restore_tasks(self) -> Dict:
        """Get all restore tasks"""
        return self.get_documents_by_prefix('restore_task:')

    # Maintenance operations

    def save_maintenance(self, maintenance_id: str, data: Dict) -> bool:
        """Save maintenance entry"""
        doc = data.copy()
        doc['type'] = 'maintenance'
        return self.save_document(self.db, f'maintenance:{maintenance_id}', doc)

    def load_all_maintenance(self) -> Dict:
        """Load all maintenance entries"""
        return self.get_documents_by_prefix('maintenance:')

    # Live stats operations (for API access when bot is separate)

    def save_live_stats(self, stats: Dict) -> bool:
        """Save live stats snapshot"""
        doc = stats.copy()
        doc['type'] = 'live_stats'
        return self.save_document(self.db, 'live_stats', doc)

    def load_live_stats(self) -> Optional[Dict]:
        """Load live stats snapshot"""
        doc = self.get_document(self.db, 'live_stats')
        if doc and 'type' in doc:
            doc = {k: v for k, v in doc.items() if k != 'type'}
        return doc

# Global instance
_couchdb_client = None

def get_couchdb_client() -> CouchDBClient:
    """Get or create the global CouchDB client instance"""
    global _couchdb_client
    if os.getenv("COUCHDB_DISABLED", "0") == "1":
        return _NullCouchDBClient()
    if _couchdb_client is None:
        _couchdb_client = CouchDBClient()
    return _couchdb_client


class _CouchDBWriteWorker:
    """Serialize and coalesce CouchDB writes in a background thread."""
    def __init__(self, client: CouchDBClient):
        self._client = client
        self._queue = queue.Queue()
        self._pending: Dict[str, Tuple[Any, str, Dict]] = {}
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, name="couchdb-writer", daemon=True)
        self._thread.start()

    def _make_key(self, db, doc_id: str) -> str:
        return f"{id(db)}:{doc_id}"

    def enqueue(self, db, doc_id: str, data: Dict) -> None:
        key = self._make_key(db, doc_id)
        with self._lock:
            is_new = key not in self._pending
            self._pending[key] = (db, doc_id, data)
        if is_new:
            self._queue.put(key)

    def _run(self) -> None:
        while True:
            key = self._queue.get()
            with self._lock:
                item = self._pending.pop(key, None)
            if not item:
                continue
            db, doc_id, data = item
            self._client._save_document_sync(db, doc_id, data)


class _NullCouchDBClient:
    """No-op CouchDB client for voice-only mode."""
    def get_document(self, db, doc_id: str, default: Any = None) -> Any:
        return default

    def save_document(self, db, doc_id: str, data: Dict) -> bool:
        return True

    def get_all_documents(self, db) -> Dict:
        return {}

    def get_documents_by_prefix(self, prefix: str) -> Dict:
        return {}

    def load_user_data(self) -> Dict:
        return {}

    def save_user_data(self, user_data: Dict) -> bool:
        return True

    def get_user_stats(self, user_id: str) -> Optional[Dict]:
        return None

    def save_user_stats(self, user_id: str, stats: Dict) -> bool:
        return True

    def load_usernames(self) -> Dict:
        return {}

    def save_usernames(self, usernames: Dict) -> bool:
        return True

    def load_servernames(self) -> Dict:
        return {}

    def save_servernames(self, servernames: Dict) -> bool:
        return True

    def load_voice_time_data(self) -> Dict:
        return {}

    def save_voice_time_data(self, voice_time_data: Dict) -> bool:
        return True

    def save_audio_state(self, state_data: Dict) -> bool:
        return True

    def load_audio_state(self) -> Optional[Dict]:
        return None

    def delete_audio_state(self) -> bool:
        return True

    def save_restore_task(self, guild_id: str, task_data: Dict) -> bool:
        return True

    def load_restore_task(self, guild_id: str) -> Optional[Dict]:
        return None

    def delete_restore_task(self, guild_id: str) -> bool:
        return True

    def get_all_restore_tasks(self) -> Dict:
        return {}

    def save_live_stats(self, stats: Dict) -> bool:
        return False

    def load_live_stats(self) -> Optional[Dict]:
        return None
