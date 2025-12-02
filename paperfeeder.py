from argparse import ArgumentParser
import logging
import os
import datetime
from dotenv import load_dotenv
import arxiv
from rich import pretty, print
from rich.console import Console
from rich.markdown import Markdown
import pandas as pd
from RSSInfra.Article import article
from RSSInfra.Summarizer import sakura_summarizer, gemini_summarizer, openai_summarizer, custom_summarizer
from sqlalchemy import create_engine, MetaData, Table, Column, String, DateTime, Text, Integer, inspect, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.exc import OperationalError

logger = logging.getLogger("paperfeeder")


def save_papers_to_db(df, category, host, port, user, password, db_name):
    """
    Saves the given DataFrame of papers to the specified database using SQLAlchemy.
    """
    db_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"
    try:
        engine = create_engine(db_url)
        metadata = MetaData()

        # Check if migration is needed
        insp = inspect(engine)
        if insp.has_table("papers"):
            columns = [c['name'] for c in insp.get_columns("papers")]
            if "id" not in columns:
                logger.info("Migrating database schema: Adding 'id' column...")
                with engine.connect() as conn:
                    # Drop existing primary key (which was url)
                    try:
                        conn.execute(text("ALTER TABLE papers DROP PRIMARY KEY"))
                    except Exception as e:
                        logger.warning(f"Could not drop primary key: {e}")

                    # Add id column
                    conn.execute(text("ALTER TABLE papers ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY FIRST"))

                    # Add unique constraint to url if not exists (it was PK so it is likely unique, but let's ensure)
                    try:
                        conn.execute(text("ALTER TABLE papers ADD UNIQUE (url)"))
                    except Exception as e:
                        logger.warning(f"Could not add unique constraint to url: {e}")

                    conn.commit()
                logger.info("Database migration complete.")

        papers_table = Table(
            'papers', metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('url', String(255), unique=True),
            Column('title', String(512)),
            Column('authors', Text),
            Column('published', DateTime),
            Column('updated', DateTime),
            Column('summary', Text),
            Column('category', String(255))
        )
        
        metadata.create_all(engine, checkfirst=True)

        df_for_db = df.drop(columns=['No']).rename(columns={
            'Title': 'title',
            'Authors': 'authors',
            'Published': 'published',
            'Updated': 'updated',
            'Summary': 'summary',
            'URL': 'url'
        })

        df_for_db['published'] = df_for_db['published'].dt.tz_localize(None)
        df_for_db['updated'] = df_for_db['updated'].dt.tz_localize(None)
        
        papers_to_insert = df_for_db.to_dict('records')

        for paper in papers_to_insert:
            paper['category'] = category

        if not papers_to_insert:
            logger.info("No papers to save.")
            return

        stmt = mysql_insert(papers_table).values(papers_to_insert)
        
        update_stmt = stmt.on_duplicate_key_update(
            updated=stmt.inserted.updated,
            published=stmt.inserted.published,
            summary=stmt.inserted.summary,
            category=stmt.inserted.category,
            title=stmt.inserted.title,
            authors=stmt.inserted.authors
        )

        with engine.connect() as conn:
            conn.execute(update_stmt)
            conn.commit()
            
        logger.info("Saved %d papers to the database", len(df))

    except OperationalError as e:
        logger.error(f"Database connection failed: {e}", exc_info=True)
        print(f"Error: Could not connect to the database at {host}:{port}. Please check your database credentials and network connection.")
        raise
    except Exception as e:
        logger.error(f"An error occurred while saving papers: {e}", exc_info=True)
        raise

def to_dataframe(papers):
    i = 1
    data = []
    for paper in papers:
        data.append({
            "No": i,
            "Title": paper.title,
            "Authors": ", ".join(author.name for author in paper.authors),
            "Published": paper.published,
            "Updated": paper.updated,
            "Summary": paper.summary,
            "URL": paper.entry_id,
        })
        i += 1
    df = pd.DataFrame(data)
    return df

def main():
    load_dotenv()

    parser = ArgumentParser(description="PaperFeeder Command Line Interface")
    parser.add_argument("--log-level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Set the logging level")
    parser.add_argument("--delta-days", type=int, default=None,
                        help="Number of days to look back for new papers")
    parser.add_argument("--category", type=str, default="cs.AI",)
    parser.add_argument("--max-results", type=int, default=None,
                        help="Maximum number of results to fetch from arXiv")
    parser.add_argument("--max-items", type=int, default=20,
                        help="Maximum number of items to include in the summary")
    parser.add_argument("--save", action="store_true", default=False,
                        help="Save the fetched papers to the database")

    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "3306"))
    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "paperfeeder")

    args = parser.parse_args()

    loglevel = args.log_level.upper()

    global logger
    logger = logging.getLogger("paperfeeder")
    logger.setLevel(getattr(logging, loglevel))
    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, loglevel))
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    logger.info("PaperFeeder started with log level: %s", loglevel)

    category = os.getenv("CATEGORY", args.category)

    if args.category:
        category = args.category

    delta_days = int(os.getenv("DELTA_DAYS", "10"))

    if args.delta_days:
        delta_days = args.delta_days

    max_results = int(os.getenv("MAX_RESULTS", "100"))

    if args.max_results:
        max_results = args.max_results
    
    max_items = int(os.getenv("MAX_ITEMS", 20))

    if args.max_items:
        max_items = args.max_items

    logger.info("Fetching papers in category: %s for the last %d days", category, delta_days)
    logger.debug("Using max results: %d", max_results)

    now = datetime.datetime.utcnow()
    start_date = now - datetime.timedelta(days=delta_days)

    logger.info("Papers from %s to %s", start_date.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))
    arxiv_start_date = start_date.strftime("%Y%m%d0000")
    arxiv_end_date = now.strftime("%Y%m%d2359")

    logger.debug("arXiv API start date parameter: %s", arxiv_start_date)
    logger.info("Simulating fetching papers from arXiv API...")

    query = ""
    query += f"cat:{category}"
    query += f" AND submittedDate:[{arxiv_start_date} TO {arxiv_end_date}]"

    logger.debug("arXiv API query: %s", query)

    client = arxiv.Client()

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    logger.info("Executing search...")
    results = client.results(search)
    papers = list(results)

    logger.info("Found %d papers", len(papers))

    if not papers:
        logger.info("No new papers found in the last %d days for category %s", delta_days, category)
    else:
        logger.debug("New papers found:")
        for paper in papers:
            logger.debug("Title: %s, Authors: %s, Published: %s", paper.title, ", ".join(author.name for author in paper.authors), paper.published)

    df = to_dataframe(papers)

    if args.save and papers:
        save_papers_to_db(df, category, db_host, db_port, db_user, db_password, db_name)

    summarizer = None

    if papers:
        articles = article.articlesFromDataframe(df)

        summarizer_method = os.getenv("SUMMARIZE_METHOD", "gemini").lower()

        logger.info("Using summarization method: %s", summarizer_method)

        response = None

        if summarizer_method == 'gemini':
            summarizer = gemini_summarizer.GeminiSummarizer(None, None)
        elif summarizer_method == 'sakura':
            summarizer = sakura_summarizer.SakuraSummarizer(None, None)
        elif summarizer_method == 'openai':
            summarizer = openai_summarizer.OpenAISummarizer(None, None)
        elif summarizer_method == 'custom':
            summarizer = custom_summarizer.CustomSummarizer(None, None)

        if summarizer:
            response = summarizer.summarize(articles, max_items=max_items)
        
        if response:
            logger.info("Summary:\n%s", response)

    canonical_date = now.strftime("%Y-%m-%d")
    frontmatter = f"""---
title: "New Papers from arXiv"
date: {canonical_date}
tags: ["arXiv", "{category.replace('.', '-')}"]
---"""
    
    md_content = frontmatter + "\n\n"
    for index, row in df.iterrows():
        md_content += f"## {row['No']}. {row['Title']}\n"
        md_content += f"**Authors:** {row['Authors']}\n\n"
        md_content += f"**Published:** {row['Published'].strftime('%Y-%m-%d')}\n\n"
        md_content += f"**Updated:** {row['Updated'].strftime('%Y-%m-%d')}\n\n"
        md_content += f"**URL:** [Link]({row['URL']})\n\n"
        md_content += f"**Summary:**\n\n{row['Summary']}\n\n"
        md_content += "---\n\n"
    
    console = Console()

    if response:
        console.print(Markdown("## Summary"))
        console.print(Markdown(response.text))
    
    clipping_path = os.getenv("CLIPPING_PATH", None)

    if clipping_path:
        if not os.path.exists(clipping_path):
            os.makedirs(clipping_path)

        filename = f"papers_{category.replace('.', '_')}_{canonical_date}.md"
        filepath = os.path.join(clipping_path, filename)

        if os.path.exists(filepath):
            logger.warning("File already exists")
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(frontmatter + "\n\n")
                f.write("# " + category.replace('.', '_') + canonical_date + "\n\n")

                for row in df.itertuples():
                    f.write(f"## {row.No}. {row.Title}\n")
                    f.write(f"**Authors:** {row.Authors}\n\n")
                    f.write(f"**Published:** {row.Published.strftime('%Y-%m-%d')}\n\n")
                    f.write(f"**Updated:** {row.Updated.strftime('%Y-%m-%d')}\n\n")
                    f.write(f"**URL:** [Link]({row.URL})\n\n")
                    f.write(f"**Summary:**\n\n{row.Summary}\n\n")
                    f.write("---\n\n")
                
                if response:
                    f.write("## Summary\n\n")
                    f.write(response.text + "\n")

        logger.info("Markdown file saved to: %s", filepath)

if __name__ == "__main__":
    main()
