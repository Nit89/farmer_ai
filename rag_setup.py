# rag_setup.py
import time
from typing import List
from pathlib import Path

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    DirectoryLoader, PyPDFLoader, UnstructuredFileLoader, RecursiveUrlLoader
)
from langchain_core.documents import Document
from bs4 import BeautifulSoup as Soup


# ---------------- Website Extractor ----------------
def extract_website(url: str, max_depth: int = 2, retries: int = 3) -> List[Document]:
    loader = RecursiveUrlLoader(
        url,
        max_depth=max_depth,
        extractor=lambda x: Soup(x, "html.parser").text,
        prevent_outside=True,
        use_async=True,
        timeout=1200,
        check_response_status=True
    )

    attempt = 0
    while attempt < retries:
        try:
            documents = loader.load()
            print(f"✅ Extracted {len(documents)} docs from {url}" ,documents)
            return documents
        except Exception as e:
            print(f"❌ Failed {url} on attempt {attempt + 1}: {e}")
            attempt += 1
            time.sleep(2 ** attempt)

    return []


# ---------------- Main RAG Setup ----------------
def build_vector_db():
    docs_folder = "docs"
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    # Load local docs
    pdf_loader = DirectoryLoader(docs_folder, glob="**/*.pdf", loader_cls=PyPDFLoader)
    txt_loader = DirectoryLoader(docs_folder, glob="**/*.txt", loader_cls=UnstructuredFileLoader)

    documents = pdf_loader.load() + txt_loader.load()
    print(f"📄 Loaded {len(documents)} local documents")

    # Load websites
    websites = [
        "https://www.fao.org/statistics/en/",
        "https://icar.org.in/",
    ]
    for url in websites:
        documents.extend(extract_website(url, max_depth=2))

    print(f"📚 Total documents (local + web): {len(documents)}")

    # Split docs into chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=80)
    chunks = text_splitter.split_documents(documents)

    # Save to Chroma
    vectordb = Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory="chroma")
    vectordb.persist()
    print("✅ Vector DB created at ./chroma")


if __name__ == "__main__":
    build_vector_db()

