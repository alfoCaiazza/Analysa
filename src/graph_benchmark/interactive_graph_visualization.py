from tqdm import tqdm
from pyvis.network import Network
import networkx as nx
from torch_geometric.utils import to_networkx
import torch

obj = torch.load('src/data/graph_data.pt', weights_only=False)
data = obj['data']
idx2user = obj['idx2user']

# Creating the graph G
G_nx = to_networkx(data, edge_attrs=['edge_weight'])

# Mapping idx to user names
mapping = {i: idx2user[i] for i in G_nx.nodes()}
G_nx = nx.relabel_nodes(G_nx, mapping)

# PyVis initialization
net = Network(height="800px", width="100%", bgcolor="#222", font_color="white")

# Visualizing the adding process for both nodes and edges with tqdm
print("Adding nodes:")
for node in tqdm(G_nx.nodes(), desc="Nodes"):
    net.add_node(node, label=str(node), size=15)
print("Adding edges:")
for u, v, d in tqdm(G_nx.edges(data=True), desc="Edges"):
    net.add_edge(u, v, value=d.get('edge_weight', 1.0))

# net.show("graph.html", notebook=False) -> when using a notebook
net.write_html("graph_v1.html")

