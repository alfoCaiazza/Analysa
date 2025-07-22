import sqlite3
import csv
import pandas as pd

connection = sqlite3.connect('reddit-posts.db')
cursor = connection.cursor()

# Retrieving all the nodes (aka reddit users) with an engagement score greater than x
# The engagement score is the sum of the number of comments and replies made by the user
cursor.execute('''
    SELECT author, SUM(engagement) AS total_engagement
    FROM(
        SELECT author, SUM(num_comments) AS engagement
        FROM posts
        GROUP BY author
            UNION ALL
        SELECT author, SUM(num_replies) AS engagement
        FROM comments
        GROUP BY author
    ) AS combined
    GROUP BY author
    HAVING total_engagement > ?
''', (10,))

distinct_users = cursor.fetchall()

print(f"Total distinct users : {len(distinct_users)}")
print(f"Example of user : {distinct_users[0]}")

# Retrieving edges type author-commenter where the author has more than x interactions with the commenter
cursor.execute('''
    SELECT p.author AS src, c.author as dst, COUNT(*) as weight
    FROM posts AS p
    JOIN comments AS c ON p.id = c.post_id
    GROUP BY p.author, c.author
    HAVING weight > ?
''', (2,))

edges_type_ac = cursor.fetchall()

print(f"Total edges a-to-c identified: {len(edges_type_ac)}")
print(f"Example of edge a-to-c : {edges_type_ac[0]}")

# Retrieving edges type commenter-commenter where the commenter has more than x interactions with the parent commenter
cursor.execute('''
    SELECT child.author AS src, parent.author AS dst, COUNT(*) as weight
    FROM comments AS parent
    JOIN comments AS child ON parent.comment_id = child.parent_id 
    GROUP BY child.author, parent.author
    HAVING weight > ?
''', (2,))

edges_type_cc = cursor.fetchall()

print(f"Total edges c-to-c identified: {len(edges_type_cc)}")
print(f"Example of edge c-to-c : {edges_type_cc[0]}")

print(f"Total edges identified: {len(edges_type_ac) + len(edges_type_cc)}")

# Creating nodes csv file
with open('src/data/nodes.csv', 'w') as csv_file:
    writer = csv.writer(csv_file, delimiter=',')
    writer.writerow(['id', 'engagement'])
    writer.writerows(distinct_users)

# Creating edges csv file
with open('src/data/edges.csv', 'w') as csv_file:
    writer = csv.writer(csv_file, delimiter=',')
    writer.writerow(['source', 'target', 'weight'])
    writer.writerows(edges_type_ac)
    writer.writerows(edges_type_cc)