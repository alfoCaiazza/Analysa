from prawcore.exceptions import PrawcoreException
from praw.exceptions import RedditAPIException
from dotenv import load_dotenv
import praw
import os
import logging
import pandas as pd
import time
import sqlite3
from datetime import datetime, timezone
import random
from prawcore.exceptions import RequestException, ResponseException, ServerError

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
    )

# Database set-up functions
# Creating main table
def create_tables(conn):
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS posts(
        id TEXT PRIMARY KEY,
        subreddit TEXT,
        author TEXT,
        title TEXT,
        date TEXT,
        text TEXT,
        num_comments INTEGER,
        over_18 INTEGER,
        score INTEGER
    )      
    '''
    )

    c.execute('''
        CREATE TABLE IF NOT EXISTS state (
        subreddit TEXT PRIMARY KEY,
        last_max_date TEXT)        
    ''')

    c.execute('''
       CREATE TABLE IF NOT EXISTS comments(
        post_id TEXT,
        comment_Id TEXT PRIMARY KEY,
        text TEXT,
        author TEXT,
        date TEXT,
        parent_id TEXT,
        depth INTEGER,
        num_replies INTEGER,
        score INTEGER,
        FOREIGN KEY (post_id) REFERENCES posts(id)
    )  
    '''
    )

    conn.commit()

def get_last_max_date(conn, subreddit):
    c = conn.cursor()
    c.execute('SELECT last_max_date FROM state WHERE subreddit = ?', (subreddit,))
    row = c.fetchone()
    if row and row[0]:
        return datetime.fromisoformat(row[0])
    else:
        return datetime.min.replace(tzinfo=timezone.utc)

def set_last_max_date(conn, subreddit, max_date):
    c = conn.cursor()
    c.execute(
        'INSERT OR REPLACE INTO state (subreddit, last_max_date) VALUES (?, ?)',
        (subreddit, max_date.isoformat())
    )
    conn.commit()

def reddit_scraping(subreddit, limit=None, conn=None, batch_size=100, post_per_subreddit=2000):
    # Loading database cursors
    c = conn.cursor()

    ops_since_commit = 0
    newest_date = None
    total_subreddit_posts = 0

    # Getting the oldest post in the database
    last_max_date = get_last_max_date(conn, subreddit.display_name)
    logging.info(f"Most recent post in DB: {last_max_date.isoformat()}")

    for iteration, submission in enumerate(subreddit.new(limit=limit)):
        # Skipping oldest post already in the db
        date = datetime.fromtimestamp(submission.created_utc, timezone.utc)
        if date <= last_max_date:
            logging.info(f"Reached already-scraped posts at {date.isoformat()}.")
            continue
        
        logging.info(f"Processing post {iteration + 1}: {submission.id} at {date.isoformat()}")

        if newest_date is None or date > newest_date:
            newest_date = date

        if submission.selftext == '':
            logging.info("Skipping post due to empty body text")
            continue
        
        # Getting data of the main post
        author = str(submission.author) if submission.author else "[deleted]"
        id = submission.fullname
        num_comments = submission.num_comments
        over_18 = submission.over_18
        score = submission.score
        subreddit_name = submission.subreddit.name
        title = submission.title
        text = submission.selftext

        # Insert data into db
        try:
            c.execute('''INSERT OR IGNORE INTO posts
                      (id, subreddit, author, title, date, text, num_comments, over_18, score) 
                      VALUES (?,?,?,?,?,?,?,?,?)''',
                (id, subreddit_name, author, title, date.isoformat(), text, num_comments, over_18, score))
            ops_since_commit += 1
        except Exception as e:
            logging.error(f"Failed to insert post {id}: {e}")

        # Comments processing with retry on rate limit errors
        retries = 3
        while retries > 0:
            try:
                submission.comments.replace_more(limit=None)
                for comment in submission.comments.list():
                    if comment.body == '' or comment.is_submitter:
                        continue
                    comment_id = comment.fullname
                    comment_text = comment.body
                    comment_author = str(comment.author) if comment.author else "[deleted]"
                    comment_date = datetime.fromtimestamp(comment.created_utc, timezone.utc)
                    comment_score = comment.score
                    parent_id = comment.parent_id
                    depth = comment.depth
                    num_replies = len(comment.replies)

                    c.execute('''INSERT OR IGNORE INTO comments 
                                (post_id, comment_id, text, author, date, parent_id, depth, num_replies, score)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (id, comment_id, comment_text, comment_author, comment_date.isoformat(),
                                parent_id, depth, num_replies, comment_score))
                    ops_since_commit += 1
                break  # success, esci dal retry loop
            except (RequestException, ResponseException, ServerError) as e:
                logging.warning(f"Rate limit or server error: {e}. Retrying after delay...")
                time.sleep(10)
                retries -= 1
        else:
            logging.error(f"Failed to fetch comments for post {id} after retries.")

        # Batching commits
        if ops_since_commit >= batch_size:
            conn.commit()
            logging.info(f"Committed {batch_size} posts.")
            ops_since_commit = 0

        # Sleep between posts
        total_subreddit_posts += 1
        if total_subreddit_posts > post_per_subreddit:
            break
        time.sleep(1)

    # Final commit
    if ops_since_commit > 0:
        conn.commit()
        logging.info(f"Committed final {ops_since_commit} operations.")
    
def main():
    setup_logging()
    load_dotenv()

    targeted_subreddits = ["PoliticalDiscussion", "AmItheAsshole", "offmychest", "changemyview"]

    reddit = praw.Reddit(
        client_id = os.getenv('REDDIT_CLIENT_ID'),
        client_secret = os.getenv('REDDIT_CLIENT_SECRET'),
        user_agent = os.getenv('REDDIT_USER_AGENT')
    )

    # SQL database connection
    conn = sqlite3.connect('reddit-posts.db')
    conn.execute("PRAGMA foreign_keys = ON") # Activate foreign keys
    create_tables(conn)

    start_time = time.time()

    for sub in targeted_subreddits:
        subreddit = reddit.subreddit(sub)

        logging.info(f"Scraping subreddit /r/{subreddit.display_name}")
        reddit_scraping(subreddit, conn=conn)
        time.sleep(random.uniform(8,15))

    elapsed_time = time.time() - start_time
    logging.info(f"Total execution time: {elapsed_time} s")

if __name__ == "__main__":
    main()