import sys, os
import json
import shutil
import os, re
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain.text_splitter import RecursiveCharacterTextSplitter

PROJECT_PATH = os.getenv('PROJECT_PATH', '/app')
load_dotenv(os.path.join(PROJECT_PATH, '.env'))
sys.path.append(PROJECT_PATH)

os.chdir(PROJECT_PATH)

import utils.paper_utils as pu
import utils.db.db_utils as db_utils
from utils.logging_utils import setup_logger

logger = setup_logger(__name__, "j0_doc_chunker.log")

data_path = os.path.join(os.environ.get("PROJECT_PATH"), "data", "arxiv_text")
meta_path = os.path.join(os.environ.get("PROJECT_PATH"), "data", "arxiv_meta")
child_path = os.path.join(os.environ.get("PROJECT_PATH"), "data", "arxiv_chunks")
parent_path = os.path.join(
    os.environ.get("PROJECT_PATH"), "data", "arxiv_large_chunks"
)

## Splitters setup.
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200
PARENT_CHUNK_SIZE = 10000
PARENT_CHUNK_OVERLAP = 1000
VERSION_NAME = "10000_1000"

version_name_map = {
    "10000_1000": "arxiv_large_parent_chunks",
    "2000_200": "arxiv_parent_chunks",
}

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    is_separator_regex=False,
)

parent_splitter = RecursiveCharacterTextSplitter(
    chunk_size=PARENT_CHUNK_SIZE,
    chunk_overlap=PARENT_CHUNK_OVERLAP,
    length_function=len,
    is_separator_regex=False,
)


def process_document(arxiv_code, child_path, parent_path):
    child_chunks = pu.load_local(arxiv_code, child_path, False, "json")
    parent_chunks = pu.load_local(arxiv_code, parent_path, False, "json")
    mapping = map_child_to_parent_by_content(child_chunks, parent_chunks)
    return [
        {"arxiv_code": arxiv_code, "child_id": k, "parent_id": v}
        for k, v in mapping.items()
    ]


def parallel_process_mapping(mapping_codes, child_path, parent_path):
    all_mappings = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_arxiv = {
            executor.submit(process_document, code, child_path, parent_path): code
            for code in mapping_codes
        }
        for future in tqdm(as_completed(future_to_arxiv), total=len(mapping_codes)):
            arxiv_code = future_to_arxiv[future]
            try:
                mapping_list = future.result()
                all_mappings.extend(mapping_list)
            except Exception as e:
                print(f"Document {arxiv_code} generated an exception: {e}")
    mapping_df = pd.DataFrame.from_dict(all_mappings)
    return mapping_df


def map_child_to_parent_by_content(child_chunks, parent_chunks):
    """Map child chunks to parent chunks by content."""
    mapping = {}

    for child in child_chunks:
        child_seq = child["chunk_id"]
        child_content = child["text"]
        best_parent = max(
            parent_chunks,
            key=lambda parent: (
                len(child_content)
                if child_content in parent["text"]
                else next(
                    (
                        len(child_content[:end])
                        for end in range(len(child_content), 0, -1)
                        if child_content[:end] in parent["text"]
                    ),
                    0,
                )
            ),
        )
        best_match_length = (
            len(child_content)
            if child_content in best_parent["text"]
            else next(
                (
                    len(child_content[:end])
                    for end in range(len(child_content), 0, -1)
                    if child_content[:end] in best_parent["text"]
                ),
                0,
            )
        )

        if best_match_length > 0:
            mapping[child_seq] = best_parent["chunk_id"]

    return mapping


def main():
    """Chunk arxiv docs into smaller blocks."""
    arxiv_codes = pu.list_s3_files("arxiv-text", strip_extension=True)

    ## Child chunks.
    logger.info("Creating child chunks.")
    child_done = db_utils.get_arxiv_id_list("arxiv_chunks")
    child_codes = list(set(arxiv_codes) - set(child_done))
    logger.info(f"Found {len(child_codes)} child papers pending.")

    for idx, arxiv_code in enumerate(child_codes):
        ## Open doc and meta_data.
        doc_txt = pu.load_local(arxiv_code, data_path, relative=False, format="txt", s3_bucket="arxiv-text")
        logger.info(f"[{idx}/{len(child_codes)}] Processing {arxiv_code}.")
        doc_texts = text_splitter.split_text(doc_txt)
        doc_chunks = [doc.replace("\n", " ") for doc in doc_texts]

        ## Store document chunks in DB.
        doc_chunks_df = pd.DataFrame.from_dict(doc_chunks)
        doc_chunks_df["arxiv_code"] = arxiv_code
        doc_chunks_df["chunk_id"] = doc_chunks_df.index
        doc_chunks_df.columns = ["text", "arxiv_code", "chunk_id"]
        db_utils.upload_dataframe(doc_chunks_df, "arxiv_chunks", pu.db_params)

        ## Store document chunks in JSON.
        doc_chunks_list = doc_chunks_df.to_dict(orient="records")
        pu.store_local(doc_chunks_list, arxiv_code, child_path, relative=False, format="json")
        pu.upload_s3_file(arxiv_code, "arxiv-chunks", prefix="data", format="json")

    ## Parent chunks.
    logger.info("Creating parent chunks.")
    parent_table_name = version_name_map[VERSION_NAME]
    parent_done = db_utils.get_arxiv_id_list(pu.db_params, parent_table_name)
    parent_codes = list(set(arxiv_codes) - set(parent_done))
    logger.info(f"Found {len(parent_codes)} parent papers pending.")

    for idx, arxiv_code in enumerate(parent_codes):
        ## Open doc and meta_data.
        doc_txt = pu.load_local(arxiv_code, data_path, relative=False, format="txt", s3_bucket="arxiv-text")
        doc_texts = parent_splitter.split_text(doc_txt)
        doc_chunks = [doc.replace("\n", " ") for doc in doc_texts]

        ## Store document chunks in DB.
        doc_chunks_df = pd.DataFrame.from_dict(doc_chunks)
        doc_chunks_df["arxiv_code"] = arxiv_code
        doc_chunks_df["chunk_id"] = doc_chunks_df.index
        doc_chunks_df.columns = ["text", "arxiv_code", "chunk_id"]
        db_utils.upload_dataframe(doc_chunks_df, parent_table_name, pu.db_params)

        ## Store document chunks in JSON.
        doc_chunks_list = doc_chunks_df.to_dict(orient="records")
        pu.store_local(doc_chunks_list, arxiv_code, parent_path, relative=False, format="json")
        pu.upload_s3_file(arxiv_code, "arxiv-chunks", prefix="data", format="json")

    ## Mapping of child-to-parent.
    logger.info("Mapping child-to-parent.")
    ## ToDo: Allow version param here.
    mapping_done = db_utils.get_arxiv_id_list(pu.db_params, "arxiv_chunk_map")
    mapping_codes = list(set(arxiv_codes) - set(mapping_done))
    logger.info(f"Found {len(mapping_codes)} mapping papers pending.")

    mapping_df = parallel_process_mapping(mapping_codes, child_path, parent_path)
    mapping_df["version"] = VERSION_NAME
    db_utils.upload_dataframe(mapping_df, "arxiv_chunk_map", pu.db_params)


if __name__ == "__main__":
    main()
