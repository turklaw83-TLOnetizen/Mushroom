from core.storage.base import StorageBackend
from core.storage.json_backend import JSONStorageBackend
from core.storage.encrypted_backend import (
    EncryptedStorageBackend,
    derive_encryption_key,
    get_or_create_salt,
    is_encryption_enabled,
    enable_encryption_marker,
    verify_passphrase,
    write_verification_token,
    encrypt_existing_data,
)

# PostgresStorageBackend is imported lazily to avoid requiring
# SQLAlchemy when only using JSON/Encrypted backends.
def get_postgres_backend_class():
    from core.storage.postgres_backend import PostgresStorageBackend
    return PostgresStorageBackend

__all__ = [
    "StorageBackend",
    "JSONStorageBackend",
    "EncryptedStorageBackend",
    "derive_encryption_key",
    "get_or_create_salt",
    "is_encryption_enabled",
    "enable_encryption_marker",
    "verify_passphrase",
    "write_verification_token",
    "encrypt_existing_data",
    "get_postgres_backend_class",
]

