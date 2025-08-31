import pandas as pd
import sqlite3
import numpy as np
from tqdm import tqdm
import csv
from collections import Counter

# Connecting to database
connection = sqlite3.connect('reddit-posts.db')
cursor = connection.cursor()

# Getting valid users
df = pd.read_csv('src/data/nodes.csv')
users = df['id'].tolist()

# Retriving all texts for both posts and comments tables
cursor.execute('''
    SELECT p.author, p.id, p.text, 'post' AS type, p.date
    FROM posts as p
    WHERE p.text <> '[removed]' AND p.date >= '2025-01-01'
        UNION ALL
    SELECT c.author, c.comment_Id, c.text, 'comment' AS type, c.date
    FROM comments as c
    WHERE c.text <> '[removed]' AND c.date >= '2025-01-01'
''')

res = cursor.fetchall()
cursor.close()

print(f"Operation sample: {res[0]}")

# Retrieving valid users
users = pd.read_csv('src/data/nodes.csv')
users_id = users['id'].tolist()
valid_users_set =set(users_id)

count = 0

# Writing results in a csv file
with open('src/nlp/raw_textual_df.csv', 'w') as csv_file:
    writer = csv.writer(csv_file, delimiter=',')
    writer.writerow(['author', 'id', 'text', 'type', 'date'])

    for row in res:
        if row[0] in valid_users_set:
            count += 1
            writer.writerow(row)

print(f"Total texts retrieved: {len(res)}")
print(f"Total texts with valid user: {count}")