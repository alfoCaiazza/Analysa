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
        Id TEXT PRIMARY KEY,
        Subreddit TEXT,
        Author TEXT,
        Title TEXT,
        Date TEXT,
        Text TEXT,
        Num_comments INTEGER,
        Over_18 INTEGER,
        Score INTEGER
    )      
    '''
    )

    c.execute('''
       CREATE TABLE IF NOT EXISTS comments(
        Post_id TEXT,
        Comment_Id TEXT PRIMARY KEY,
        Text TEXT,
        Author TEXT,
        Date TEXT,
        Parent_id TEXT,
        Depth INTEGER,
        Num_replies INTEGER,
        Score INTEGER,
        FOREIGN KEY (Post_id) REFERENCES posts(Id)
    )  
    '''
    )

    conn.commit()

def get_last_after(conn, subreddit):
    c = conn.cursor()
    c.execute('SELECT after FROM state WHERE subreddit = ?', (subreddit,))
    res = c.fetchone()
    return res[0] if res else ''

def set_last_after(conn,subreddit, after):
    c = conn.cursor()
    c.execute('DELETE FROM state')
    c.execute('INSERT INTO state (subreddit, after) VALUES (?,?)', (subreddit,after))

    conn.commit()

def reddit_scraping(subreddit, limit=None, conn=None, batch_size=100):
    # Loading database cursors
    c = conn.cursor()

    ops_since_commit = 0

    # Getting the oldest post in the database
    c.execute('SELECT MAX(date) FROM posts')
    row = c.fetchone()
    max_date = row[0]
    if max_date is not None:
        max_date = datetime.fromisoformat(max_date)
    else:
        max_date = datetime.min.replace(tzinfo=timezone.utc)

    logging.info(f"Most recent post in DB: {max_date.isoformat()}")

    for iteration, submission in enumerate(subreddit.new(limit=limit)):
        # Skipping oldest post already in the db
        date = datetime.fromtimestamp(submission.created_utc, timezone.utc)
        if date <= max_date:
            logging.info(f"Reached already-scraped posts at {date.isoformat()}, stopping.")
            break
        
        logging.info(f"Processing post {iteration + 1}/{limit}")

        if submission.selftext == '':
            logging.info("Skipping post due to empty body text")
            continue
        
        # Getting data of the main post
        author = str(submission.author) if submission.author else "[deleted]"
        id = submission.id
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

        # Getting data of the comments tree
        try:
            submission.comments.replace_more(limit=None)
            for comment in submission.comments.list():
                if comment.body == '' or comment.is_submitter: # Skipping empty comments or comments where the author is the same of the root post
                    continue
                comment_id = comment.id
                comment_text = comment.body
                comment_author = str(comment.author) if comment.author else "[deleted]"
                comment_date = datetime.fromtimestamp(comment.created_utc, timezone.utc)
                comment_score = comment.score
                parent_id = comment.parent_id
                depth = comment.depth
                num_replies = len(comment.replies)

                c.execute('''
                        INSERT OR IGNORE INTO comments 
                        (post_id, comment_id, text, author, date, parent_id, depth, num_replies, score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (id, comment_id, comment_text, comment_author, comment_date.isoformat(), parent_id, depth, num_replies, comment_score)
                )
                ops_since_commit += 1
        except Exception as e:
            logging.error(f"Failed to process comments for post {id}: {e}")

        # Batching commits
        if ops_since_commit >= batch_size:
            conn.commit()
            logging.info(f"Committed {batch_size} posts.")
            ops_since_commit = 0

    # Final commit
    if ops_since_commit > 0:
        conn.commit()
        logging.info(f"Committed final {ops_since_commit} operations.")
    
def main():
    setup_logging()
    load_dotenv()

    targeted_subreddits = ["AskEurope"]

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
        time.sleep(10)
        subreddit = reddit.subreddit(sub)

        logging.info(f"Scraping subreddit /r/{subreddit.display_name}")
        reddit_scraping(subreddit, conn=conn)

    
    elapsed_time = time.time() - start_time
    logging.info(f"Total execution time: {elapsed_time} ms")

if __name__ == "__main__":
    main()