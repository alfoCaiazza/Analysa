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
        score INTEGER,
        upvote_ratio REAL
    )      
    ''')

    c.execute('''
       CREATE TABLE IF NOT EXISTS comments(
        post_id TEXT,
        comment_id TEXT PRIMARY KEY,
        text TEXT,
        author TEXT,
        date TEXT,
        parent_id TEXT,
        depth INTEGER,
        num_replies INTEGER,
        score INTEGER,
        FOREIGN KEY (post_id) REFERENCES posts(id)
    )  
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS scraping_state (
            subreddit TEXT PRIMARY KEY,
            newest_processed_utc REAL
        )
    ''')

    conn.commit()

def get_last_timestamp(conn, subreddit_name):
    c = conn.cursor()
    c.execute('SELECT newest_processed_utc FROM scraping_state WHERE subreddit = ?', (subreddit_name,))
    row = c.fetchone()

    if row:
        logging.info(f"Found existing timestamp for r/{subreddit_name}: {datetime.fromtimestamp(row[0])}")
        return row[0]
    else:
        logging.info(f"No existing timestamp for r/{subreddit_name}. Starting from beginning.")
        return 0  # Starting from beginning if first-time scraping

def set_last_timestamp(conn, subreddit_name, timestamp_utc):
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO scraping_state (subreddit, newest_processed_utc)
        VALUES (?, ?)
    ''', (subreddit_name, timestamp_utc))

    conn.commit()

def reddit_scraping(subreddit, conn=None, max_posts_per_session=1000, batch_size=100):
    subreddit_name = subreddit.display_name
    
    # Retrieving last known timestamp in the db
    last_known_timestamp = get_last_timestamp(conn, subreddit_name)
    
    current_session_newest = None
    posts_processed = 0
    ops_since_commit = 0
    total_comments_processed = 0
    
    try:
        for submission in subreddit.new(limit=None):
            if posts_processed >= max_posts_per_session:
                logging.info(f"Reached max limit {max_posts_per_session} posts per session")
                break
            
            post_created_utc = submission.created_utc
            
            # Updtaed with the newest post of the current session
            if current_session_newest is None or post_created_utc > current_session_newest:
                current_session_newest = post_created_utc

            if post_created_utc < last_known_timestamp:
                logging.info(f"Reached already-processed posts ({(datetime.fromtimestamp(post_created_utc))}). Exiting.")
                break
            
            try:
                posts_processed, ops_since_commit, comments_count = process_submission(
                    submission, conn, posts_processed, ops_since_commit, batch_size
                )
                total_comments_processed += comments_count
                
            except Exception as e:
                logging.error(f"ERROR for submission {submission.id}: {e}. Skipping.")
                continue
            
            # 8. Random sleep between posts
            time.sleep(random.uniform(1, 3))
    
    except Exception as e:
        logging.error(f"ERROR in r/{subreddit_name}: {e}")
    
    finally:
        # Final commit
        if ops_since_commit > 0:
            conn.commit()
            logging.info(f"Final commit di {ops_since_commit} ops")
        
        # If new posts have been found then updated the state param
        if current_session_newest is not None and current_session_newest > last_known_timestamp:
            logging.info(f"UPDATING newest_processed_utc for r/{subreddit_name} a {datetime.fromtimestamp(current_session_newest)}")
            set_last_timestamp(conn, subreddit_name, current_session_newest)
        
        logging.info(f"SCRAPE ENDED for r/{subreddit_name}. Processed: {posts_processed} post, {total_comments_processed} comments")

def process_submission(submission, conn, posts_processed, ops_since_commit, batch_size):
    c = conn.cursor()
    comments_processed = 0

    logging.info(f"Processing post {submission.id}")
    
    # Skip post with empty body - images or other objs
    if not submission.selftext or submission.selftext.strip() == '':
        logging.debug(f"Skipping post {submission.id} - empty body")
        return posts_processed, ops_since_commit, comments_processed
    
    post_data = {
        'id': submission.id,
        'subreddit_name': submission.subreddit.display_name,
        'author': str(submission.author) if submission.author else "[deleted]",
        'title': submission.title,
        'date': datetime.fromtimestamp(submission.created_utc, timezone.utc).isoformat(),
        'text': submission.selftext,
        'num_comments': submission.num_comments,
        'score': submission.score,
        'upvote_ratio': submission.upvote_ratio
    }
    
    try:
        c.execute('''INSERT OR IGNORE INTO posts
                  (id, subreddit, author, title, date, text, num_comments, score, upvote_ratio) 
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (post_data['id'], post_data['subreddit_name'], post_data['author'], 
             post_data['title'], post_data['date'], post_data['text'], 
             post_data['num_comments'], post_data['score'],post_data['upvote_ratio']))
        ops_since_commit += 1
    except Exception as e:
        logging.error(f"ERROR during post loading {submission.id}: {e}")
        return posts_processed, ops_since_commit, comments_processed
    
    # Separatelly processing comments
    comments_processed = process_comments(submission, conn, ops_since_commit)
    ops_since_commit += comments_processed
    
    # Commit batch
    if ops_since_commit >= batch_size:
        conn.commit()
        ops_since_commit = 0
    
    posts_processed += 1
    logging.debug(f"Procesed post {submission.id} with {comments_processed} comments")
    
    return posts_processed, ops_since_commit, comments_processed

def process_comments(submission, conn, initial_ops_count):
    c = conn.cursor()
    comments_processed = 0
    ops_count = initial_ops_count
    
    retries = 3
    while retries > 0:
        try:
            # Expand hidden comments (MoreComments)
            submission.comments.replace_more(limit=None)
            
            for comment in submission.comments.list():
                # Skip empty comments or of automod
                if (not comment.body or comment.body.strip() == '' or 
                    getattr(comment.author, 'name', '') == 'AutoModerator'):
                    continue
                
                comment_data = {
                    'post_id': submission.id,
                    'comment_id': comment.id,
                    'text': comment.body,
                    'author': str(comment.author) if comment.author else "[deleted]",
                    'date': datetime.fromtimestamp(comment.created_utc, timezone.utc).isoformat(),
                    'parent_id': comment.parent_id,
                    'depth': getattr(comment, 'depth', 0),
                    'num_replies': len(comment.replies) if hasattr(comment, 'replies') else 0,
                    'score': getattr(comment, 'score', 0)
                }

                try:
                    c.execute('''INSERT OR IGNORE INTO comments 
                              (post_id, comment_id, text, author, date, parent_id, depth, num_replies, score)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (comment_data['post_id'], comment_data['comment_id'], comment_data['text'],
                            comment_data['author'], comment_data['date'], comment_data['parent_id'],
                            comment_data['depth'], comment_data['num_replies'], comment_data['score']))
                    ops_count += 1
                    comments_processed += 1
                    
                except Exception as e:
                    logging.error(f"ERROR during comment insertion {comment.id}: {e}")
                    continue
            
            break
            
        except (RequestException, ResponseException, ServerError, PrawcoreException) as e:
            retry_delay = 30 * (4 - retries)  # Exponential Backoff: 30, 60, 90 sec
            logging.warning(f"SERVER ERROR ({e}). Retry in {retry_delay}s... (Tries {4-retries}/3)")
            time.sleep(retry_delay)
            retries -= 1
    else:
        logging.error(f"FAILED fetching post's comments {submission.id}")
    
    return comments_processed
    
def main():
    setup_logging()
    load_dotenv()

    targeted_subreddits = ["PoliticalDiscussion", "AmItheAsshole", "offmychest", "changemyview", "TrueAskReddit", "unpopularopinion", "confession"] 

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