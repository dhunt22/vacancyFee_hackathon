import json

path = "C:/Users/devin/Desktop/Claude/vacancyFee_gis/hackathon_data/starter_notebook.ipynb"

with open(path) as f:
    nb = json.load(f)

nb['cells'][6]['source'] = [
    "## Fee Revenue Projection\n",
    "\n",
    "Model revenue under a **square-footage-based graduated fee** that ramps up the longer a property sits vacant.\n",
    "\n",
    "This fee applies to **parcels with structures** (using `BUILDING_SQFT` or `LIVING_SQFT`). Bare vacant land without buildings remains at the current $70 flat fee.\n",
    "\n",
    "| Vacancy Duration | Rate per Sq Ft per Month |\n",
    "| --- | --- |\n",
    "| 0 to 3 months | $0.00 (grace period) |\n",
    "| 4 to 6 months | $0.50 |\n",
    "| 7 to 9 months | $0.75 |\n",
    "| 10 to 12 months | $1.00 |\n",
    "| 13 to 24 months | $2.00 |\n",
    "| 25 to 36 months | $3.00 |\n",
    "| 37 to 48 months | $4.00 |\n",
    "| 49+ months | +$1.00 per sqft for each additional 12-month period |"
]

with open(path, 'w') as f:
    json.dump(nb, f, indent=1)

# Verify
with open(path) as f:
    nb2 = json.load(f)
for line in nb2['cells'][6]['source']:
    print(repr(line))
