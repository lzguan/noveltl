from functools import lru_cache

from botocore.config import Config

from src.files.config import file_store_settings
from src.files.storage import ObjectStore, S3ObjectStore


@lru_cache
def get_object_store() -> ObjectStore:
    """Return the process-wide configured object store."""
    access_key_id = file_store_settings.AWS_ACCESS_KEY_ID
    secret_access_key = file_store_settings.AWS_SECRET_ACCESS_KEY
    if access_key_id is None or secret_access_key is None:
        raise RuntimeError("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required to use file storage")

    return S3ObjectStore(
        endpoint_url=file_store_settings.S3_ENDPOINT_URL,
        region=file_store_settings.S3_REGION,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key.get_secret_value(),
        bucket=file_store_settings.S3_BUCKET,
        config=Config(s3={"addressing_style": file_store_settings.S3_ADDRESSING_STYLE}),
    )
