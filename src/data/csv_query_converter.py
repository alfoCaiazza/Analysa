import sqlite3
import csv
from collections import Counter, defaultdict
import math
import numpy as np

# Database connection
connection = sqlite3.connect('reddit-posts.db')
cursor = connection.cursor()

# User retrieval and engagement computation
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
''')

distinct_users = cursor.fetchall()
all_users = {user: count for user, count in distinct_users}

# Computing engagement value distribuition
engagement_values = np.array(list(all_users.values()))

# Cutoff
engagement_cutoff = np.quantile(engagement_values, 0.8)  # keepin 20% most active users
print(f"Engagement threshold: {engagement_cutoff}")
valid_users = {user for user, count in all_users.items() if count >= engagement_cutoff}
print(f"Users after engagement filter: {len(valid_users)}")

# Edges post→comment
cursor.execute('''
    SELECT p.author AS src, c.author as dst, COUNT(*) as weight
    FROM posts AS p
    JOIN comments AS c ON p.id = c.post_id
    GROUP BY p.author, c.author
    HAVING (p.author <> '[deleted]' AND c.author <> '[deleted]')
       AND (p.author <> c.author)
       AND (p.text <> '[removed]' AND c.text <> '[removed]')
''')
edges_type_ac = cursor.fetchall()

# Edges comment→comment
cursor.execute('''
    SELECT 
        c1.author AS src, 
        c2.author AS dst, 
        COUNT(*) as weight
    FROM comments c1
    JOIN comments c2 ON SUBSTR(c1.parent_id, 4) = c2.comment_id
    WHERE c1.author <> '[deleted]' 
        AND c2.author <> '[deleted]'
        AND c1.text <> '[removed]'
        AND c2.text <> '[removed]'
        AND c1.author <> c2.author
        AND c1.parent_id LIKE 't1_%'
    GROUP BY c1.author, c2.author
''')
edges_type_cc = cursor.fetchall()

# Filtering valid users
filtered_edges = [
    (src, dst, weight) for src, dst, weight in edges_type_ac + edges_type_cc
    if src in valid_users and dst in valid_users
]

print(f"Edges after user filter: {len(filtered_edges)}")

# Making edges undirectioned
edge_dict = defaultdict(int)
for src, dst, w in filtered_edges:
    u, v = sorted([src, dst]) 
    edge_dict[(u, v)] += w

# Normalizzazione log(1+w)
final_edges = [(u, v, math.log1p(w)) for (u, v), w in edge_dict.items()]
print(f"Unique undirected edges: {len(final_edges)}")

# Computing degree value distribuition
degree_counter = Counter()
for u, v, w in final_edges:
    degree_counter[u] += 1
    degree_counter[v] += 1

degree_values = np.array([deg for user, deg in degree_counter.items()])

# Cutoff
degree_cutoff = np.quantile(degree_values, 0.5)
print(f"Degree threshold: {degree_cutoff}")
final_users = {user for user in valid_users if degree_counter[user] >= degree_cutoff}

final_edges = [(u, v, w) for u, v, w in final_edges if u in final_users and v in final_users]
final_nodes = [(user, all_users[user]) for user in final_users]

print(f"Final filtered users: {len(final_nodes)}")
print(f"Final edges count: {len(final_edges)}")

# CSV saving process
with open('src/data/nodes.csv', 'w') as csv_file:
    writer = csv.writer(csv_file, delimiter=',')
    writer.writerow(['id', 'engagement'])
    writer.writerows(final_nodes)

with open('src/data/edges.csv', 'w') as csv_file:
    writer = csv.writer(csv_file, delimiter=',')
    writer.writerow(['source', 'target', 'weight'])
    writer.writerows(final_edges)

print("Nodes and edges CSV exported successfully.")
