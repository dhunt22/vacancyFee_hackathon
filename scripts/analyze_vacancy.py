import pandas as pd

cols = ['PARCEL_APN','USE_CODE_MUNI','USE_CODE_MUNI_DESC','VAL_ASSD_IMPRV','VAL_ASSD_LAND','VAL_ASSD',
        'LIVING_SQFT','BUILDING_SQFT','YR_BLT','SITE_CITY']
df = pd.read_csv('C:/Users/devin/Desktop/Claude/vacancyFee_gis/data/sacramento_identified_parcels.csv', usecols=cols, low_memory=False)
df['code_str'] = df['USE_CODE_MUNI'].astype(str).str.strip()

# Residential parcels with zero improvement value (potential dilapidated/demolished)
res_zero = df[(df['code_str'].str.startswith('A')) & ((df['VAL_ASSD_IMPRV'] == 0) | (df['VAL_ASSD_IMPRV'].isna()))]
print('=== RESIDENTIAL CODES (A) WITH ZERO IMPROVEMENT VALUE ===')
print(f'Total: {len(res_zero)}')
print(res_zero['USE_CODE_MUNI_DESC'].value_counts().head(15))
print()

# Commercial/retail parcels with zero improvement
comm_zero = df[(df['code_str'].str.startswith('B')) & ((df['VAL_ASSD_IMPRV'] == 0) | (df['VAL_ASSD_IMPRV'].isna()))]
print('=== COMMERCIAL/RETAIL (B) WITH ZERO IMPROVEMENT VALUE ===')
print(f'Total: {len(comm_zero)}')
print(comm_zero['USE_CODE_MUNI_DESC'].value_counts().head(15))
print()

# Office with zero improvement
off_zero = df[(df['code_str'].str.startswith('C')) & ((df['VAL_ASSD_IMPRV'] == 0) | (df['VAL_ASSD_IMPRV'].isna()))]
print(f'=== OFFICE (C) WITH ZERO IMPROVEMENT: {len(off_zero)} ===')
print(off_zero['USE_CODE_MUNI_DESC'].value_counts().head(10))
print()

# Industrial with zero improvement
ind_zero = df[(df['code_str'].str.startswith('G')) & ((df['VAL_ASSD_IMPRV'] == 0) | (df['VAL_ASSD_IMPRV'].isna()))]
print(f'=== INDUSTRIAL (G) WITH ZERO IMPROVEMENT: {len(ind_zero)} ===')
print(ind_zero['USE_CODE_MUNI_DESC'].value_counts().head(10))
print()

# Value distribution of explicit vacant parcels
explicit = df[df['code_str'].str.startswith('I')]
print('=== VALUE DISTRIBUTION OF VACANT PARCELS ===')
print(explicit['VAL_ASSD_LAND'].describe())
print()
print('Value brackets:')
brackets = [0, 50000, 100000, 250000, 500000, 1000000, float('inf')]
labels = ['<50K', '50K-100K', '100K-250K', '250K-500K', '500K-1M', '>1M']
explicit['bracket'] = pd.cut(explicit['VAL_ASSD_LAND'], bins=brackets, labels=labels)
print(explicit['bracket'].value_counts().sort_index())
print()
total_val = explicit['VAL_ASSD_LAND'].sum()
print(f'Total assessed land value of vacant parcels: ${total_val:,.0f}')

# City distribution
print()
print('=== VACANT PARCELS BY CITY ===')
print(explicit['SITE_CITY'].value_counts().head(15))
