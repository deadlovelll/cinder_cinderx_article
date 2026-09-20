from recsys.settings import Settings


def embedding_store_impl(settings: Settings):
    if settings.embeddings == "numpy":
        from recsys.infrastructure.embeddings.numpy_embedding_store import NumpyEmbeddingStore

        return NumpyEmbeddingStore
    if settings.embeddings == "static":
        from recsys.infrastructure.embeddings.static_embedding_store import StaticEmbeddingStore

        return StaticEmbeddingStore
    from recsys.infrastructure.embeddings.python_embedding_store import PythonEmbeddingStore

    return PythonEmbeddingStore
