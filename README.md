# Study Guide Generator

This application turns a course document into a study guide.

It accepts a `.pdf` or `.pptx` file, extracts the text from each page or slide, retrieves the most relevant sections for the user request, and sends that context to an LLM to generate a structured study guide.

## What It Does

- Reads lecture slides or class documents from PDF and PowerPoint files
- Extracts text page-by-page or slide-by-slide
- Uses a lightweight local retrieval step to find the most relevant sections
- Generates a study guide focused on key ideas, definitions, processes, and relationships
- Produces student-facing output with section headings and a short review checklist

## Requirements

- Python 3.12+
- A document with selectable text
- One of the following model options:
  - `ollama` for a local model
  - `litellm` for a remote model using your own API key

## Setup

Create and activate a virtual environment if you want an isolated install:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the Python dependencies:

```bash
pip install .
```

If `pip install .` does not work in your environment, install the required packages directly:

```bash
pip install pypdf litellm llama-index llama-index-llms-litellm
```

## Run With Ollama

The default backend is `ollama`, so this is the simplest way to run the app without using an API key.

1. Install Ollama
2. Pull a model:

```bash
ollama pull llama3.1:8b
```

3. Run the generator:

```bash
python3 main.py /path/to/document.pdf
```

or

```bash
python3 main.py /path/to/slides.pptx
```

You can also choose a different local model:

```bash
export OLLAMA_MODEL="llama3.1:8b"
python3 main.py /path/to/document.pdf
```

## Run With a Remote API

If you want to use the `litellm` backend, you must provide your own API key.

Set these environment variables before running:

```bash
export LITELLM_API_KEY="your-api-key"
export LITELLM_API_BASE="https://llm-api.cyverse.ai/v1"
export LITELLM_MODEL="js2/gpt-oss-120b"
```

`LITELLM_API_BASE` and `LITELLM_MODEL` have defaults in the script, but `LITELLM_API_KEY` is required for the remote backend.

Run the app with:

```bash
python3 main.py /path/to/document.pdf --backend litellm
```

or

```bash
python3 main.py /path/to/slides.pptx --backend litellm
```

## Common Options

Override the default study-guide request:

```bash
python3 main.py /path/to/document.pdf --question "Generate a study guide focused on definitions and cause-effect relationships."
```

Change how many sections are retrieved for the final prompt:

```bash
python3 main.py /path/to/document.pdf --top-k 6
```

## How It Works

1. The application extracts text from each PDF page or PowerPoint slide.
2. It builds local TF-IDF vectors from the extracted text.
3. It retrieves the most relevant sections for the user request.
4. It sends the retrieved context to the selected LLM backend.
5. It prints the generated study guide in the terminal.

## Notes

- The input file must be a `.pdf` or `.pptx`
- The document must contain selectable text; scanned images without OCR will not work well
- If you use the remote backend, you are responsible for supplying your own API key
