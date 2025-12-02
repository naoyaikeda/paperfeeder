# Changelog

All notable changes to this project will be documented in this file.

## [0.2.1] - 2025-12-02

### Fixed
- Implemented a feature to replace the “.” in categories used for tags with “-”.

## [Unreleased] - 2025-12-02

### Added
- `--save` flag to enable saving fetched papers to a MySQL database.
- Database connection settings can be configured via environment variables (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`).

### Changed
- Refactored database logic to use SQLAlchemy for more robust and maintainable code, replacing the previous `mysql.connector` implementation.
- The `save_papers_to_db` function now performs an "upsert" (INSERT ... ON DUPLICATE KEY UPDATE) to add new papers or update existing ones.
- The database table schema is now managed within the script and the `papers` table is created automatically if it doesn't exist.
- Updated database schema to use an auto-incrementing `id` as the primary key. Existing `papers` tables will be automatically migrated to include the `id` column, and the `url` column will become a unique key.

### Fixed
- Corrected a database schema error where the primary key on the `url` column was too long for some MySQL configurations.
- Fixed a `CompileError` caused by an extra "No" column in the data being sent to the database.
- Resolved a database error by converting timezone-aware `datetime` objects from the arXiv API to timezone-naive ones compatible with MySQL's `DATETIME` type.

## [0.1.0] - 2025-12-01

### Added
- Initial release of PaperFeeder.
- Feature to fetch papers from arXiv based on category and date range.
- Summarization support using multiple LLM backends:
    - Gemini (Google)
    - Sakura (Sakura Internet)
    - OpenAI (GPT models)
    - Custom (OpenAI-compatible APIs)
- Output to console with rich formatting.
- Export of paper details and summaries to Markdown files.
- Configuration via command-line arguments and environment variables.