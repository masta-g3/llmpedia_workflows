# Repository Structure

```
llmpedia/
├── app.py                    # Main Streamlit application
├── requirements.txt          # Core production dependencies
├── requirements_dev.txt      # Development dependencies
├── Dockerfile                # Container configuration
├── docker-compose.yml        # Container orchestration
├── workflow.sh               # Main workflow execution script
├── tweet_collector.sh        # Tweet collection script
├── update_and_restart.sh     # Deployment update script
├── daily_update.sh           # Daily update automation script
├── weekly_review.sh          # Weekly review automation script
├── run_tweet_sender.sh       # Script for sending tweets
│
├── config/                   # Configuration files
│   └── tweet_types.yaml      # Tweet generation configuration
│
├── workflow/                 # Core processing pipeline modules
│   ├── a0_scrape_lists.py      # Twitter list scraping
│   ├── a1_scrape_tweets.py     # Tweet scraping
│   ├── b0_download_paper.py    # Paper download logic
│   ├── b1_download_paper_marker.py  # Paper download tracking
│   ├── c0_fetch_meta.py        # Metadata fetching
│   ├── d0_summarize.py         # Paper summarization
│   ├── e0_narrate.py           # Narrative generation
│   ├── e1_narrate_bullet.py    # Bullet point narratives
│   ├── e2_data_card.py         # Data card generation
│   ├── e2_narrate_punchline.py # Punchline generation
│   ├── f0_review.py            # Review generation
│   ├── g0_create_thumbnail.py  # Thumbnail creation
│   ├── h0_citations.py         # Citation processing
│   ├── i0_generate_embeddings.py  # Embedding generation
│   ├── i1_topic_model.py       # Topic modeling
│   ├── i2_similar_docs.py      # Document similarity
│   ├── i3_topic_map.py         # Topic mapping
│   ├── j0_doc_chunker.py       # Document chunking
│   ├── k0_rag_embedder.py      # RAG embedding
│   ├── l0_abstract_embedder.py # Abstract embedding
│   ├── m0_page_extractor.py    # Page extraction
│   ├── n0_repo_extractor.py    # Repository extraction
│   ├── z0_update_gist.py       # Update gist workflow
│   ├── z1_generate_tweet.py    # Tweet generation
│   ├── z2_generate_tweet.py    # Configuration-driven tweet generation
│   └── z3_schedule_reply.py    # Tweet reply scheduling
│
├── utils/                    # Utility modules and helpers
│   ├── app_utils.py           # Application utilities
│   ├── data_cards.py          # Data card utilities
│   ├── custom_langchain.py    # Custom LangChain implementations
│   ├── embeddings.py          # Embedding utilities
│   ├── instruct.py            # Instruction utilities
│   ├── db/                    # Database operations modules
│   │   ├── __init__.py          # Package initialization
│   │   ├── db_utils.py          # Core database utilities
│   │   ├── paper_db.py          # Paper-related operations
│   │   ├── tweet_db.py          # Tweet-related operations
│   │   ├── embedding_db.py      # Embedding-related operations
│   │   └── logging_db.py        # Logging-related operations
│   ├── prompts.py             # LLM prompt templates
│   ├── vector_store.py        # Vector storage operations
│   ├── paper_utils.py         # Paper processing utilities
│   ├── tweet.py               # Tweet processing utilities
│   ├── streamlit_utils.py     # Streamlit UI utilities
│   ├── pydantic_objects.py    # Data models
│   ├── plots.py               # Visualization utilities
│   ├── styling.py             # UI styling
│   ├── logging_utils.py       # Logging configuration
│   ├── notifications.py       # Notification system
│   └── tweet_generation/      # Tweet generation utilities
│
├── prompts/                  # LLM prompt templates
│   ├── __init__.py             # Package initialization
│   ├── aux_prompts.py          # Auxiliary prompts
│   ├── llmpedia_prompts.py     # LLMpedia specific prompts
│   ├── qna_prompts.py          # Question and answer prompts
│   ├── react_prompts.py        # ReAct prompts
│   ├── tweet_prompts.py        # Tweet generation prompts
│   ├── weekly_prompts.py       # Weekly review prompts
│   └── workflow_prompts.py     # Workflow prompts
│
├── executors/                # Task execution modules
│   ├── a1_daily_update.py      # Daily update about new papers
│   ├── a3_tweet_sender.py      # Tweet sending script
│   ├── b1_weekly_review.py     # Weekly review generation
│   ├── c1_tweet_reply.py       # Tweet reply workflow script
│   ├── collect_tweets.py       # Tweet collection script
│   ├── image_gallery.py        # Image gallery generation
│   ├── t0_analyze_tweets.py    # Tweet analysis script
│   ├── delete_paper.py         # Paper deletion utility
│   ├── summarize_extended.py   # Extended summarization
│   ├── check_corrupt_pdfs.py   # PDF corruption checker
│   ├── batch_s3_upload.py      # S3 batch upload utility
│   └── my_aesthetic_predictor.py # Aesthetic prediction utility
│
├── notebooks/                # Jupyter notebooks for analysis
├── sql/                      # SQL scripts and schemas
├── data/                     # Data storage
├── artifacts/                # Generated artifacts
├── logs/                     # Application logs
├── temp_files/               # Temporary file storage
├── deprecated/               # Deprecated code and files
│
├── .streamlit/              # Streamlit configuration
├── .env                     # Environment variables
├── .gitignore              # Git ignore rules
├── README.md               # Project documentation
├── STRUCTURE.md            # Repository structure documentation
├── VERSIONS.md             # Version history
├── CHANGES.md              # Change log
├── DISCUSSION.md           # Discussion notes
└── PLANNING.md             # Development planning
```

## Directory Overview

### Core Components
- `app.py`: Main Streamlit application serving the web interface
- `workflow/`: Contains the sequential processing pipeline modules (a0 → z3)
- `utils/`: Shared utility functions and helper modules
- `executors/`: Task execution and scheduling modules
- `prompts/`: LLM prompt templates for various tasks

### Data and Storage
- `data/`: Raw and processed data storage
- `artifacts/`: Generated outputs and artifacts
- `logs/`: Application and process logs
- `sql/`: Database schemas and SQL scripts
- `temp_files/`: Temporary file storage

### Configuration
- `.env`: Environment variables and configuration
- `.streamlit/`: Streamlit-specific configuration
- `config/`: Configuration files
- `requirements.txt`: Production dependencies
- `requirements_dev.txt`: Development dependencies

### Documentation
- `README.md`: Project overview and setup instructions
- `STRUCTURE.md`: Repository structure documentation
- `VERSIONS.md`: Version history and changelog
- `CHANGES.md`: Detailed change log
- `DISCUSSION.md`: Discussion notes
- `PLANNING.md`: Development planning and tracking
- `notebooks/`: Analysis and development notebooks

### Deployment
- `Dockerfile`: Container image definition
- `docker-compose.yml`: Container orchestration
- `update_and_restart.sh`: Deployment update script
- `workflow.sh`: Main workflow execution script
- `tweet_collector.sh`: Tweet collection automation
- `daily_update.sh`: Shell script that runs daily updates at 7 PM PST/PDT, with progress tracking and logging functionality
- `weekly_review.sh`: Shell script that runs weekly reviews every Monday at 2:00 PM PST/PDT, using the previous Monday's date as input
- `run_tweet_sender.sh`: Script for sending tweets

## Utils Directory (`utils/`)

### Database Operations (`utils/db/`)
- `db_utils.py`: Core database utilities and helper functions
  - Connection management
  - Query execution
  - Common SQL operations
- `paper_db.py`: Paper-related database operations
  - Loading paper details
  - Managing summaries and topics
  - Handling citations and repositories
- `tweet_db.py`: Tweet-related database operations
  - Storing and reading tweets
  - Managing tweet analyses and replies
- `embedding_db.py`: Embedding-related database operations
  - Storing and loading embeddings
  - Managing embedding dimensions
- `logging_db.py`: Logging-related database operations
  - Token usage tracking
  - Error logging
  - Q&A and visit logging
  - Workflow execution logging

### Vector Store Operations (`utils/vector_store.py`)
- `vector_store.py`: Vector storage operations
  - Connection management
  - Embedding operations
  - LLM query functions
  - Tweet generation and reply functions
  
### Other Utilities
- `app_utils.py`: Application utilities
- `data_cards.py`: Data card generation utilities
- `custom_langchain.py`: Custom LangChain implementations
- `embeddings.py`: Embedding generation and processing
- `instruct.py`: Instruction formatting utilities
- `paper_utils.py`: Paper processing utilities
- `tweet.py`: Tweet processing utilities
- `streamlit_utils.py`: Streamlit UI utilities
- `pydantic_objects.py`: Data models
- `plots.py`: Visualization utilities
- `styling.py`: UI styling
- `logging_utils.py`: Logging configuration
- `notifications.py`: Notification system

## Prompts Directory (`prompts/`)
- `aux_prompts.py`: Auxiliary prompts for miscellaneous tasks
- `llmpedia_prompts.py`: LLMpedia-specific prompts
- `qna_prompts.py`: Question and answer-related prompts
- `react_prompts.py`: ReAct framework-related prompts
- `tweet_prompts.py`: Tweet generation and reply prompts
- `weekly_prompts.py`: Weekly review generation prompts
- `workflow_prompts.py`: Workflow process prompts
