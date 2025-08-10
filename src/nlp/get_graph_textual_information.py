import pandas as pd
import sqlite3
import numpy as np
from tqdm import tqdm
import csv
from collections import Counter

# Connecting to database
connection = sqlite3.connect('reddit-posts.db')
cursor = connection.cursor()

# Retriving all texts for both posts and comments tables
cursor.execute('''
    SELECT p.author, p.text, 'post' AS type
    FROM posts as p
        UNION ALL
    SELECT c.author, c.text, 'comment' AS type
    FROM comments as c
''')

res = cursor.fetchall()
cursor.close()

print(f"Total texts retrieved: {len(res)}")
print(f"Operation sample: {res[0]}")

# Writing results in a csv file
with open('src/nlp/raw_textual_df.csv', 'w') as csv_file:
    writer = csv.writer(csv_file, delimiter=',')
    writer.writerow(['author', 'text', 'type'])
    writer.writerows(res)