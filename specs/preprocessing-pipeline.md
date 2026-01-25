# Attachment Preprocessing Pipeline

Technical overview of how PDF and image attachments are preprocessed before the Arbie agent runs.

## Pipeline Overview

```mermaid
flowchart TB
    subgraph Input["Email Reception"]
        EMAIL[/"Inbound Email"/]
        ATT1["PDF Attachments"]
        ATT2["Image Attachments"]
    end

    subgraph Storage["Azure Blob Storage"]
        BLOB_ATT["/attachments/*<br/>(read-only)"]
        BLOB_EXT["/extracted/*<br/>(read-only)"]
    end

    subgraph DB["Database"]
        ATT_REC["Attachment Records<br/>status: PENDING"]
        ATT_PROC["Attachment Records<br/>status: PROCESSED"]
    end

    subgraph PDFProcessing["PDF Processing (Mistral OCR)"]
        MISTRAL["Mistral OCR API<br/>mistral-ocr-latest"]
        TEXT_OUT["Extracted Text<br/>(markdown)"]
        IMG_OUT["Extracted Images<br/>(base64 decoded)"]
    end

    subgraph Classification["Image Classification (RunPod)"]
        CLIP["CLIP Zero-Shot<br/>Classification"]
        LABELS["Room Type Labels:<br/>bedroom, kitchen, bathroom,<br/>living_room, outdoor, pool,<br/>document, other..."]
        CATEGORIZED["Images Grouped<br/>by Room Type"]
    end

    subgraph VisionAnalysis["Room Metadata Extraction (OpenAI)"]
        VISION["GPT-5.2 Vision API"]
        PROMPT["file_processor.md<br/>prompt template"]
        ROOMS["Room Metadata JSON:<br/>- room name<br/>- objects list<br/>- image references"]
    end

    subgraph Output["Preprocessed Data"]
        META_FILE["room_meta_{ts}.json"]
        AGENT["Arbie Agent"]
    end

    %% Flow
    EMAIL --> ATT1 & ATT2
    ATT1 & ATT2 --> |store_attachment| BLOB_ATT
    BLOB_ATT --> ATT_REC

    ATT1 --> |signed URL| MISTRAL
    MISTRAL --> TEXT_OUT & IMG_OUT
    TEXT_OUT --> |extracted_text field| ATT_PROC
    IMG_OUT --> |store images| BLOB_EXT
    BLOB_EXT --> |extracted_metadata IDs| ATT_PROC

    ATT2 --> |collect URLs| CLIP
    IMG_OUT --> |extracted image URLs| CLIP
    CLIP --> LABELS
    LABELS --> CATEGORIZED

    CATEGORIZED --> VISION
    PROMPT --> VISION
    VISION --> ROOMS
    ROOMS --> META_FILE
    META_FILE --> BLOB_EXT

    BLOB_ATT & BLOB_EXT & ATT_PROC --> AGENT
```

## Detailed Step Sequence

```mermaid
sequenceDiagram
    participant Email as Inbound Email
    participant Store as Azure Blob
    participant DB as Database
    participant Main as main.py
    participant Pre as file_preprocessing.py
    participant Mistral as Mistral OCR
    participant RunPod as RunPod CLIP
    participant OpenAI as OpenAI Vision
    participant Agent as Arbie Agent

    Email->>Store: store_attachment()
    Store-->>DB: Create attachment record (PENDING)

    Main->>Pre: preprocess_and_classify()

    rect rgb(240, 248, 255)
        Note over Pre,Mistral: PDF Processing
        Pre->>Store: Get signed URL for PDF
        Pre->>Mistral: extract_images_and_text(url)
        Mistral-->>Pre: {text, images[]}
        Pre->>Store: Store extracted images to /extracted/
        Pre->>DB: Update PDF attachment (extracted_text, extracted_metadata)
    end

    rect rgb(255, 248, 240)
        Note over Pre,RunPod: Image Classification
        Pre->>RunPod: classify_images(all_image_urls)
        RunPod-->>Pre: [{url, predictions[]}]
        Pre->>Pre: categorize_images_by_room()
    end

    rect rgb(240, 255, 240)
        Note over Pre,OpenAI: Room Metadata Extraction
        loop For each room type
            Pre->>OpenAI: analyze images with file_processor.md prompt
            OpenAI-->>Pre: [{name, objects[], attachments[]}]
        end
        Pre->>Store: Store room_meta_{ts}.json
    end

    Pre->>DB: Update all statuses to PROCESSED
    Pre-->>Main: Return attachment IDs
    Main->>Agent: Run with preprocessed data
```

## Virtual File System After Preprocessing

```mermaid
graph LR
    subgraph VFS["Virtual File System (per session)"]
        subgraph ATT["/attachments/ (read-only)"]
            A1["photo1.jpg"]
            A2["photo2.png"]
            A3["document.pdf"]
            A4["floor_plan.pdf"]
        end

        subgraph EXT["/extracted/ (read-only, auto-generated)"]
            E1["document_page_0_img_0.jpeg"]
            E2["document_page_1_img_0.jpeg"]
            E3["floor_plan_page_0_img_0.jpeg"]
            E4["room_meta_20240125_120000.json"]
        end

        subgraph WS["/workspace/ (read-write)"]
            W1["agent working files"]
        end

        subgraph OUT["/outputs/ (generated)"]
            O1["property_summary.pdf"]
        end
    end
```

## Data Model

```mermaid
erDiagram
    Email ||--o{ Attachment : contains
    Attachment ||--o{ Attachment : "extracts (via extracted_metadata)"

    Attachment {
        string id PK
        string email_id FK
        string filename
        string content_type
        int size_bytes
        string storage_path
        string checksum
        AttachmentStatus status
        string extracted_text
        list extracted_metadata
        datetime uploaded_at
        datetime processed_at
    }
```

## External Services

| Service | Purpose | API |
|---------|---------|-----|
| **Mistral OCR** | PDF text & image extraction | `mistral-ocr-latest` model |
| **RunPod** | CLIP zero-shot image classification | Serverless endpoint |
| **OpenAI Vision** | Room clustering & object detection | `gpt-5.2` with vision |
| **Azure Blob** | File storage | Blob Storage SDK |

## CLIP Classification Labels

The RunPod endpoint uses these labels for zero-shot classification:

```
bedroom, kitchen, living_room, bathroom, outdoor, pool,
dining_room, balcony, terrace, garage, garden, document, other
```

Each label is prefixed with "a photo of a " (e.g., "a photo of a bedroom") for CLIP compatibility.
