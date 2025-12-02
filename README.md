# PaperFeeder

PaperFeeder is an automated tool designed to fetch the latest academic papers from arXiv, organize them, and generate summaries using various Large Language Models (LLMs). It outputs the results to the console and saves detailed reports as Markdown files.

## Features

- **arXiv Fetching**: Automatically fetches papers from specified arXiv categories within a defined date range.
- **Multi-LLM Summarization**: Supports multiple LLM backends for generating summaries:
  - **Gemini** (Google)
  - **Sakura** (Sakura Internet)
  - **OpenAI** (GPT models)
  - **Custom** (Any OpenAI-compatible API, e.g., local LLMs)
- **Rich Output**: Displays formatted results in the console.
- **Markdown Reports**: Generates comprehensive Markdown files containing paper details and generated summaries.
- **Configurable**: Easily customizable via command-line arguments and environment variables.
- **Database Storage**: Saves fetched papers to a MySQL database with automatic schema migration (adds `id` column if missing).

## Requirements

- Python >= 3.13
- Dependencies (managed via `uv` or `pip`)

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/yourusername/paperfeeder.git
    cd paperfeeder
    ```

2.  Install dependencies:

    Using `uv` (recommended):
    ```bash
    uv sync
    ```

    Or using `pip`:
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: You may need to generate `requirements.txt` from `pyproject.toml` if it doesn't exist)*

## Usage

Run the script using Python:

```bash
python paperfeeder.py [options]
```

### Command Line Arguments

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--category` | arXiv category to fetch papers from (e.g., `cs.AI`, `cs.CL`) | `cs.AI` |
| `--delta-days` | Number of days to look back for new papers | `10` |
| `--max-results` | Maximum number of papers to fetch from arXiv | `100` |
| `--max-items` | Maximum number of items to include in the generated summary | `20` |
| `--log-level` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) | `INFO` |

### Environment Variables

You can configure the behavior and API keys using a `.env` file or environment variables.

**General Configuration:**

- `CATEGORY`: Default arXiv category.
- `DELTA_DAYS`: Default number of days to look back.
- `MAX_RESULTS`: Default maximum number of results.
- `MAX_ITEMS`: Default maximum items for summary.
- `CLIPPING_PATH`: Directory path to save the generated Markdown files.
- `SUMMARIZE_METHOD`: The LLM backend to use. Options: `gemini`, `sakura`, `openai`, `custom`. (Default: `gemini`)

**LLM Configuration:**

Depending on the `SUMMARIZE_METHOD` selected, specific environment variables are required:

- **Gemini (`SUMMARIZE_METHOD=gemini`):**
  - `API_KEY`: Your Google API Key.
  - `MODEL_NAME`: Gemini model name (Default: `gemini-2.5-flash`).

- **OpenAI (`SUMMARIZE_METHOD=openai`):**
  - `API_KEY`: Your OpenAI API Key.
  - `MODEL_NAME`: OpenAI model name (e.g., `gpt-4o`). **Required.**
  - `TEMPERATURE`: Sampling temperature (Default: `0.7`).
  - `MAX_CHARS`: Max characters for context window safety (Default: `300000`).

- **Sakura (`SUMMARIZE_METHOD=sakura`):**
  - `API_KEY`: Your Sakura Cloud API Key.
  - `MODEL_NAME`: Sakura model name. **Required.**
  - `TEMPERATURE`: Sampling temperature (Default: `0.7`).

- **Custom (`SUMMARIZE_METHOD=custom`):**
  - `API_KEY`: API Key for the custom endpoint.
  - `API_URL`: URL of the custom API (Default: `http://localhost:1234/v1`).
  - `MODEL_NAME`: Model name. **Required.**
  - `TEMPERATURE`: Sampling temperature (Default: `0.7`).

## Example

Fetch papers from `cs.LG` (Machine Learning) for the last 3 days, using the OpenAI backend, and save the report to the `clippings` folder.

1.  Set environment variables (or use `.env`):
    ```bash
    export SUMMARIZE_METHOD=openai
    export API_KEY=sk-...
    export MODEL_NAME=gpt-4o
    export CLIPPING_PATH=./clippings
    ```

2.  Run the command:
    ```bash
    python paperfeeder.py --category cs.LG --delta-days 3
    ```

## License

See [license.txt](license.txt).
