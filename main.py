from argparse import ArgumentParser
import logging
import os
import datetime
from dotenv import load_dotenv
import arxiv

logger = None

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
        logger.info("New papers found:")
        for paper in papers:
            logger.info("Title: %s, Authors: %s, Published: %s", paper.title, ", ".join(author.name for author in paper.authors), paper.published)

if __name__ == "__main__":
    main()
