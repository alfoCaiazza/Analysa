import sqlite3
import csv
import pandas as pd

connection = sqlite3.connect('reddit-posts.db')
cursor = connection.cursor()

# Retrieving all the nodes (aka reddit users) with an engagement score greater than x
# The engagement score is the sum of an author occurrences in bot posts and comments table
cursor.execute('''
    SELECT author, COUNT(*) AS engagement
    FROM(
        SELECT p.author
        FROM posts AS p
        WHERE p.author <> '[deleted]'
            UNION ALL
        SELECT c.author
        FROM comments AS c
        WHERE c.author <> '[deleted]'
    ) GROUP BY author
    HAVING engagement >= ?
''', (10,))

distinct_users = cursor.fetchall()

print(f"Total distinct users : {len(distinct_users)}")
print(f"Example of user : {distinct_users[0]}")

valid_users = set(user[0] for user in distinct_users)

# Retrieving edges type author-commenter where the author has more than x interactions with the commenter
cursor.execute('''
    SELECT p.author AS src, c.author as dst, COUNT(*) as weight
    FROM posts AS p
    JOIN comments AS c ON p.id = c.post_id
    GROUP BY p.author, c.author
    HAVING (p.author <> '[deleted]' AND c.author <> '[deleted]') AND (p.author <> c.author)
''')

edges_type_ac = cursor.fetchall()

print(f"Total edges a-to-c identified: {len(edges_type_ac)}")
print(f"Example of edge a-to-c : {edges_type_ac[0]}")

# Retrieving edges type commenter-commenter where the commenter has more than x interactions with the parent commenter
cursor.execute('''
    SELECT child.author AS src, parent.author AS dst, COUNT(*) as weight
    FROM comments AS parent
    JOIN comments AS child ON parent.comment_id = child.parent_id 
    GROUP BY child.author, parent.author
    HAVING (child.author <> '[deleted]' AND parent.author <> '[deleted]') AND (child.author <> parent.author)
''')

edges_type_cc = cursor.fetchall()

print(f"Total edges c-to-c identified: {len(edges_type_cc)}")
print(f"Example of edge c-to-c : {edges_type_cc[0]}")

print(f"Total edges identified: {len(edges_type_ac) + len(edges_type_cc)}")

# Filtering edges to only include valid users
filtered_edges_ac =[
    (src, dst, weight) for src, dst, weight in edges_type_ac if src in valid_users and dst in valid_users
]

filtered_edges_cc = [
    (src, dst, weight) for src, dst, weight in edges_type_cc if src in valid_users and dst in valid_users
]

print(f"Total filtered edges identified: {len(filtered_edges_ac) + len(filtered_edges_cc)}")

# Creating nodes csv file
with open('src/data/nodes.csv', 'w') as csv_file:
    writer = csv.writer(csv_file, delimiter=',')
    writer.writerow(['id', 'engagement', 'num_posts', 'num_comments'])
    writer.writerows(distinct_users)

# Creating edges csv file
with open('src/data/edges.csv', 'w') as csv_file:
    writer = csv.writer(csv_file, delimiter=',')
    writer.writerow(['source', 'target', 'weight'])
    writer.writerows(filtered_edges_ac)
    writer.writerows(filtered_edges_cc)