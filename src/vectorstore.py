
import time
from functools import lru_cache

from pinecone import Pinecone, ServerlessSpec
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore

from src.config import get_settings


@lru_cache
def get_embeddings():
    s = get_settings()

    return HuggingFaceEmbeddings(
        model_name=s.embedding_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def get_pinecone_client():
    s = get_settings()

    if not s.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY is not configured")

    return Pinecone(api_key=s.pinecone_api_key)


def _wait_for_index_deletion(pc, index_name, timeout=120, interval=3):
    """Return True once the index is gone from the project, False on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        existing = {x.name for x in pc.list_indexes()}
        if index_name not in existing:
            return True
        time.sleep(interval)
    return False


def ensure_index():
    """Create the Pinecone index if needed and verify embedding dimension compatibility.

    If the configured index already exists with a different embedding dimension
    than the current model, it is deleted and recreated so vectors are stored
    and queried at the correct size.
    """

    s = get_settings()
    pc = get_pinecone_client()

    existing = {x.name for x in pc.list_indexes()}

    if s.pinecone_index_name not in existing:
        print(
            f"[pinecone] Creating index '{s.pinecone_index_name}' "
            f"(dimension={s.embedding_dimension}, metric=cosine, "
            f"cloud={s.pinecone_cloud}, region={s.pinecone_region}) ..."
        )
        pc.create_index(
            name=s.pinecone_index_name,
            dimension=s.embedding_dimension,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=s.pinecone_cloud,
                region=s.pinecone_region,
            ),
        )
    else:
        desc = pc.describe_index(s.pinecone_index_name)
        existing_dimension = getattr(desc, "dimension", None)

        if existing_dimension is None and isinstance(desc, dict):
            existing_dimension = desc.get("dimension")

        if (
            existing_dimension is not None
            and int(existing_dimension) != s.embedding_dimension
        ):
            if not s.pinecone_auto_recreate_index:
                raise RuntimeError(
                    f"Pinecone index '{s.pinecone_index_name}' has dimension "
                    f"{existing_dimension}, but {s.embedding_model} is configured "
                    f"for {s.embedding_dimension}. "
                    "Use a new index name (PINECONE_INDEX_NAME) or set "
                    "PINECONE_AUTO_RECREATE_INDEX=true to recreate it."
                )
            print(
                f"[pinecone] WARNING: index '{s.pinecone_index_name}' has dimension "
                f"{existing_dimension}, but '{s.embedding_model}' is configured for "
                f"{s.embedding_dimension}. Recreating the index with dimension "
                f"{s.embedding_dimension}; existing vectors will be lost."
            )
            pc.delete_index(s.pinecone_index_name)
            if not _wait_for_index_deletion(pc, s.pinecone_index_name):
                raise RuntimeError(
                    f"Timed out waiting for index '{s.pinecone_index_name}' "
                    "to be deleted. Delete it manually in the Pinecone console "
                    "and re-run."
                )
            pc.create_index(
                name=s.pinecone_index_name,
                dimension=s.embedding_dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=s.pinecone_cloud,
                    region=s.pinecone_region,
                ),
            )
            print(
                f"[pinecone] Index '{s.pinecone_index_name}' recreated with "
                f"dimension {s.embedding_dimension}."
            )

    return pc.Index(s.pinecone_index_name)


def get_vector_store():
    s = get_settings()

    index = ensure_index()

    return PineconeVectorStore(
        index=index,
        embedding=get_embeddings(),
        namespace=s.pinecone_namespace,
    )


def get_retriever():
    s = get_settings()

    return get_vector_store().as_retriever(
        search_kwargs={"k": s.top_k}
    )
