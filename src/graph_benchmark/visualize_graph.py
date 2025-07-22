from torch_geometric.utils import to_networkx
import torch
import matplotlib.pyplot as plt
import networkx as nx

obj = torch.load('src/data/graph_data.pt', weights_only=False)
data = obj['data']
idx2user = obj['idx2user']

G = to_networkx(data, edge_attrs=['edge_weight'])

plt.figure(figsize=(8,8))
nx.draw(G, with_labels=True, node_size=500, node_color='lightblue')
plt.show()