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

logger = None

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
canonical_date: {canonical_date}
category: {category}
categories: ["arXiv", "{category}"]
tags: ["arXiv"]
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
