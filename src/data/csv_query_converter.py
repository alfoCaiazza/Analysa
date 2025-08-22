import sqlite3
import csv
import pandas as pd
from collections import Counter

connection = sqlite3.connect('reddit-posts.db')
cursor = connection.cursor()

# Retrieving all the nodes (aka reddit users) with an engagement score greater than x
# The engagement score is the sum of an author occurrences in bot posts and comments table
cursor.execute('''
    SELECT author, COUNT(*) AS engagement
    FROM(
        SELECT p.author
        FROM posts AS p
        WHERE p.author <> '[deleted]' AND p.num_comments <> 0
            UNION ALL
        SELECT c.author
        FROM comments AS c
        WHERE c.author <> '[deleted]' AND c.num_replies <> 0
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
    SELECT 
        c1.author AS src, 
        c2.author AS dst, 
        COUNT(*) as weight
    FROM comments c1
    JOIN comments c2 ON SUBSTR(c1.parent_id, 4) = c2.comment_id
    WHERE c1.author <> '[deleted]' 
        AND c2.author <> '[deleted]'
        AND c1.author <> c2.author
        AND c1.parent_id LIKE 't1_%'
    GROUP BY c1.author, c2.author
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

# Removing users with Dregree < 2: that means users that have no interactions or that iteracted only with themselves (i.e. comment their own posts)
degree_counter = Counter()

for src, dst, weight in filtered_edges_ac + filtered_edges_cc:
    degree_counter[src] += 1
    degree_counter[dst] += 1

min_interactions = 5
final_users = {user for user, deg in degree_counter.items() if deg >= min_interactions}
final_nodes = [row for row in distinct_users if row[0] in final_users]
print(f"Total filtered users identified: {len(final_nodes)}")

# Final edges filtering
final_edges_ac = [
    (src, dst, weight) for src, dst, weight in filtered_edges_ac
    if src in final_users and dst in final_users
]

final_edges_cc = [
    (src, dst, weight) for src, dst, weight in filtered_edges_cc
    if src in final_users and dst in final_users
]

print(f"Total final edges identified: {len(final_edges_ac) + len(final_edges_cc)}")

# Creating nodes csv file
with open('src/data/nodes.csv', 'w') as csv_file:
    writer = csv.writer(csv_file, delimiter=',')
    writer.writerow(['id', 'engagement'])
    writer.writerows(final_nodes)

# Creating edges csv file
with open('src/data/edges.csv', 'w') as csv_file:
    writer = csv.writer(csv_file, delimiter=',')
    writer.writerow(['source', 'target', 'weight'])
    writer.writerows(final_edges_ac)
    writer.writerows(final_edges_cc)