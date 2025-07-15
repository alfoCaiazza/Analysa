import requests
from pprint import pprint
import sqlite3
from datetime import datetime
import time

def create_tables(conn):
    c = conn.cursor()
    c.execute('''
       CREATE TABLE IF NOT EXISTS posts(
        id TEXT PRIMARY KEY,
        title TEXT,
        score INTEGER,
        author TEXT,
        date TEXT,
        url TEXT
    )       
    '''
    )

    c.execute('''
       CREATE TABLE IF NOT EXISTS state(
            subreddit TEXT PRIMARY KEY,
            after TEXT
        )             
    ''')

    conn.commit()

def  get_last_after(conn, subreddit):
    c = conn.cursor()
    c.execute('SELECT after FROM state WHERE subreddit = ?', (subreddit,))
    res = c.fetchone()
    return res[0] if res else ''

def set_last_after(conn,subreddit, after):
    c = conn.cursor()
    c.execute('DELETE FROM state')
    c.execute('INSERT INTO state (subreddit, after) VALUES (?,?)', (subreddit,after))

    conn.commit()

def parse(subreddit, after='', conn=None):
    url_tamplate = 'https://www.reddit.com/r/{}/top.json?t=all' # dynamic url
    headers = {
        'User-Agent' : 'Analysa'
    }
    params = f'&after={after}' if after else ''
    url = url_tamplate.format(subreddit) + params # EXPLAIN
    response = requests.get(url, headers=headers)

    if response.ok:
        c = conn.cursor()
        data = response.json()['data']
        for post in data['children']:
            pdata = post['data']
            post_id = pdata['id']
            title = pdata['title']
            score = pdata['score']
            author = pdata['author']
            date = datetime.utcfromtimestamp(pdata['created_utc']).isoformat()
            url = pdata.get('url_overridden_by_dest') # get() method allows to fill the attribute with ' ' if not present

            print(f'{post_id} ({score}) {title}')
            
            c.execute('INSERT OR IGNORE INTO posts VALUES (?,?,?,?,?,?)',
                     (post_id, title, score, author, date, url) )
        conn.commit()
        return data['after']
    else:
        print(f'Error: {response.status_code}')
        return None

def main():
    subreddit = 'programming'

    # Connecting the database
    conn = sqlite3.connect('reddit-posts.db')
    create_tables(conn)


    after = get_last_after(conn, subreddit)
    try:
        while True:
            after = parse(subreddit, after, conn)
            if not after:
                break 
            set_last_after(conn, subreddit, after)
            time.sleep(2)
    except KeyboardInterrupt:
        print('Exiting ... ')
    finally:
        conn.close()

if __name__ == "__main__":
    main()
