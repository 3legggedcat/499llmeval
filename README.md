# Study Guide Generator

This project now provides a Python RAG workflow that:

- reads a `.pdf` or `.pptx` document directly
- extracts text from each page or slide
- retrieves the most relevant sections for a request
- sends a fixed study-guide prompt to a local or remote LLM
- prints a study guide grounded in the provided material

## Default setup for students

The default backend is local Ollama, so students do not need an API key.

1. Install Ollama.
2. Install the Python dependency:

```bash
pip install pypdf
```

3. Pull a local model:

```bash
ollama pull llama3.1:8b
```

4. Run the chatbot:

```bash
python3 main.py /path/to/document.pdf
```

or

```bash
python3 main.py /path/to/slides.pptx
```

You can also set a different local model:

```bash
export OLLAMA_MODEL="llama3.1:8b"
python3 main.py /path/to/document.pdf
```

## Optional remote backend

If you do want to use a remote model later, set the LLM configuration with environment variables:

```bash
export LITELLM_API_KEY="your-api-key"
export LITELLM_API_BASE="https://llm-api.cyverse.ai/v1"
export LITELLM_MODEL="js2/gpt-oss-120b"
```

`LITELLM_API_BASE` and `LITELLM_MODEL` are optional because the script has defaults.
For the remote backend, install:

```bash
pip install pypdf litellm llama-index llama-index-llms-litellm
```

## Run

```bash
python3 main.py /path/to/document.pdf
```

or

```bash
python3 main.py /path/to/slides.pptx
```

You can also override the user request or retrieval depth:

```bash
python3 main.py /path/to/document.pdf --question "Generate a study guide focused on key definitions and cause-effect relationships." --top-k 6
```

To force the remote backend:

```bash
python3 main.py /path/to/document.pdf --backend litellm
```

## How it works

`main.py` performs a lightweight RAG pipeline:

1. Extract text from PDF pages or PowerPoint slides.
2. Build local TF-IDF vectors for each section.
3. Retrieve the top matching sections for the request.
4. Combine those sections with a fixed prompt that asks the LLM to generate a study guide.

## Output format

The generated output should contain:

1. Clear study sections based on the material
2. Concise explanations of important concepts
3. A short review checklist at the bottom
