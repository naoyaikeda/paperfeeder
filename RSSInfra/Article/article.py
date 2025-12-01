import datetime
import pandas as pd

class Article:
    subject = None
    created_on_time = None

    def __init__(self, authors:str, subject:str, link:str, created_on_time):
        self.authors = authors
        self.subject = subject
        self.created_on_time = created_on_time
        self.link = link

class Articles:
    list = []

    def __init__(self):
        self.list = []

def articlesFromDataframe(df = None):
    articles = Articles()

    if df is not None and not df.empty:
        for index, row in df.iterrows():
            articles.list.append(Article(row['Authors'], row['Title'], row['URL'], row['Published']))

    return articles