# 311 Calls Heatmap Analysis

## Data Source
- `data/SacCounty_SalesForce311_calls.gpkg` (783 MB, 1,545,157 rows)
- Table: `SalesForce311`
- Geometry: POINT (each call has a location)
- Key columns: `CategoryLevel1`, `CategoryLevel2`, `CategoryName`, `Address`, `ZIP`, `Neighborhood`, `CouncilDistrictNumber`, `DateCreated`, `DateClosed`, `PublicStatus`

## Category Hierarchy
`CategoryLevel1` > `CategoryLevel2` > `CategoryName` (formatted as "Level1 Level2")

---

## Relevant Categories for Housing / Vacancy / Abandonment

### Tier 1 — Direct vacancy/abandonment indicators

| CategoryName | Count | Why it matters |
|---|---|---|
| Code Enforcement Housing - Boardup | 919 | Board-ups = confirmed abandoned/vacant buildings |
| Code Enforcement Housing - Complaint | 4,559 | Housing code violations signal neglect, potential vacancy |
| Code Enforcement Emergency Housing Repair Program - Complaint | 146 | Severe housing disrepair |

**Tier 1 total: 5,624 calls**

### Tier 2 — Strong vacancy correlation (blight indicators)

| CategoryName | Count | Why it matters |
|---|---|---|
| Code Enforcement Junk & Debris | 6,337 | Dumping/accumulation common on vacant lots |
| Code Enforcement Landscaping | 8,423 | Overgrown vegetation = neglected/vacant |
| Code Enforcement Graffiti | 6,207 | Vandalism concentrates on vacant structures |
| Code Enforcement Stagnant Water | 207 | Standing water on unmaintained lots |
| Code Enforcement Business Compliance Weeds | 680 | Weed complaints on commercial parcels |
| Code Enforcement Pest | 742 | Pest issues from neglected properties |
| Code Enforcement Pool Fence | 75 | Abandoned pool hazards |

**Tier 2 total: 22,671 calls**

### Tier 3 — Moderate vacancy correlation

| CategoryName | Count | Why it matters |
|---|---|---|
| Code Enforcement Vehicle On Street | 50,854 | Abandoned vehicles near vacant properties |
| Code Enforcement Vehicle Off Street | 3,684 | Vehicles stored on vacant lots |
| Code Enforcement Occupied Trailer Off Street | 600 | Trailers on vacant lots |
| Solid Waste Illegal Dumping | 31,003 | Illegal dumping targets vacant lots |
| Solid Waste Code Enforcement Illegal Dumping | 3,384 | Code enforcement referrals for dumping |
| Code Enforcement Work Without a Permit | 1,722 | Unauthorized construction activity |

**Tier 3 total: 91,247 calls**

### Homeless Camp categories (separate layer)

| CategoryLevel1 | Count | Notes |
|---|---|---|
| Homeless Camp | 169,627 | Encampments cluster near vacant parcels |
| Homeless Camp - Primary | 22,257 | Priority encampment reports |

**Homeless camp total: 191,884 calls**

---

## Recommended Approach

1. **Primary heatmap**: Tier 1 + Tier 2 categories (~28K calls) — strong vacancy signal
2. **Extended heatmap**: Add Tier 3 (~119K calls) — broader blight picture
3. **Homeless camp overlay**: Separate layer for correlation analysis
4. **Spatial join**: Overlay 311 heatmap with `vacant_parcels.geojson` to quantify co-occurrence

## Filter Expressions (for QGIS or Python)

### Tier 1 only
```sql
"CategoryLevel2" IN ('Housing - Boardup', 'Housing - Complaint', 'Emergency Housing Repair Program - Complaint')
```

### Tier 1 + Tier 2
```sql
"CategoryLevel1" = 'Code Enforcement'
AND "CategoryLevel2" IN (
  'Housing - Boardup',
  'Housing - Complaint',
  'Emergency Housing Repair Program - Complaint',
  'Junk & Debris',
  'Landscaping',
  'Graffiti',
  'Stagnant Water',
  'Business Compliance Weeds',
  'Pest',
  'Pool Fence'
)
```

### All Code Enforcement (broad)
```sql
"CategoryLevel1" = 'Code Enforcement'
```

### Homeless Camps
```sql
"CategoryLevel1" IN ('Homeless Camp', 'Homeless Camp - Primary')
```
