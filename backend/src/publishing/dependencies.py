from src.publishing.client import ReaderClient
from src.publishing.dispatch import PublishDispatcher, TaskiqPublishDispatcher


def get_publish_dispatcher() -> PublishDispatcher:
    return TaskiqPublishDispatcher()


def get_reader_client() -> ReaderClient:
    return ReaderClient()
