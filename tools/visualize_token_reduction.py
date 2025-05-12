import pandas as pd
import plotly.graph_objects as go
import os

# Ensure the assets directory exists
output_dir = 'assets'
os.makedirs(output_dir, exist_ok=True)
output_filename = os.path.join(output_dir, 'token_compression_visualization.png')

# Data based on user example and modification
data_dict = {
    'Sample': ['Bun', 'Crawl4AI', 'Google GenAI', 'Bun', 'Crawl4AI', 'Google GenAI'],
    'Type': ['Original', 'Original', 'Original', 'llm-min.txt', 'llm-min.txt', 'llm-min.txt'],
    'Tokens': [264588, 125332, 378374, 15973, 8526, 26825]
}
df = pd.DataFrame(data_dict)

samples = df['Sample'].unique()
original_tokens = df[df['Type'] == 'Original']['Tokens'].tolist()
reduced_tokens = df[df['Type'] == 'llm-min.txt']['Tokens'].tolist()

fig = go.Figure()

# Define bar text font size
bar_text_font_size = 11

# Original Tokens Bar
fig.add_trace(go.Bar(
    x=samples,
    y=original_tokens,
    name='Original',
    marker_color='#1f77b4',  # Blue
    text=original_tokens,
    textposition='outside', # Place text outside bar for clarity on tall bars
    texttemplate='%{y:,.0f}',
    textfont_size=bar_text_font_size
))

# Reduced Tokens Bar
fig.add_trace(go.Bar(
    x=samples,
    y=reduced_tokens,
    name='llm-min.txt',
    marker_color='#2ca02c',  # Green
    text=reduced_tokens,
    textposition='outside', # Place text outside bar
    texttemplate='%{y:,.0f}',
    textfont_size=bar_text_font_size
))

# Calculate and add percentage reduction annotations
annotations = []
for i, sample_name in enumerate(samples):
    orig_val = original_tokens[i]
    red_val = reduced_tokens[i]
    reduction_percentage = ((orig_val - red_val) / orig_val * 100) if orig_val > 0 else 0
    
    annotations.append(dict(
        x=sample_name,
        y=orig_val, # Anchor y near the top of the original bar
        text=f"<b>{reduction_percentage:.1f}% reduction</b>", # Bold text
        showarrow=False,
        font=dict(size=13, color="#222222"), # Larger, dark font
        align='center',
        yshift=25 # Shift significantly above the bar text
    ))

fig.update_layout(
    title=dict(
        text='<b>Token Count Comparison: Original vs. llm-min.txt</b>',
        x=0.5,
        font=dict(size=20, color="#222222") # Larger title
    ),
    xaxis_title=dict(
        text='Sample Project',
        font=dict(size=14, color="#222222") # Larger axis title
    ),
    yaxis_title=dict(
        text='Token Count',
        font=dict(size=14, color="#222222") # Larger axis title
    ),
    barmode='group',
    legend_title=dict(
        text='Token Type',
        font=dict(size=13, color="#222222") # Larger legend title
    ),
    legend=dict(
        font=dict(size=12, color="#222222") # Larger legend text
    ),
    plot_bgcolor='rgba(240,240,240,0.95)',
    paper_bgcolor='white',
    font=dict(family="Arial, sans-serif", size=12, color="#222222"), # Base font
    margin=dict(t=120, b=80, l=80, r=80), # Increased top margin for annotations
    annotations=annotations,
    yaxis=dict(
        gridcolor='LightGrey',
        tickformat=",.0f",
        range=[0, max(original_tokens) * 1.25] # Explicitly set range for annotation space
    ),
    xaxis=dict(
        gridcolor='LightGrey'
    )
)

# Save the plot as a static image
fig.write_image(output_filename, width=1000, height=650, scale=2) # Slightly taller for more space

print(f"Plotly visualization saved as '{output_filename}'")
print(f"Absolute path: {os.path.abspath(output_filename)}") 