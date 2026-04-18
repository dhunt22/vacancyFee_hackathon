import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# SACRAMENTO PROPERTY VALUATION ENGINE - PROP 13 CORRECTED
# Properly accounts for Proposition 13's 2% annual assessment increase cap
# ============================================================================


def build_prop13_deflator_index(start_year=1975, end_year=2026, 
                                output_file='prop13_deflator_index.csv'):
    """
    Build Proposition 13 deflator index using actual California CPI data
    
    Under Prop 13, assessed values can increase by the LESSER of:
    - 2% per year, OR
    - California Consumer Price Index (CPI) for all urban consumers
    
    This function creates a lookup table for deflating assessed values
    back to any base year using the actual Prop 13 inflation caps.
    
    Args:
        start_year: First year for index (1975 recommended - Prop 13 base)
        end_year: Last year for index
        output_file: CSV filename to save the deflator index
    
    Returns:
        DataFrame with Prop 13 deflator index
    """
    
    print("=" * 80)
    print("BUILDING PROPOSITION 13 DEFLATOR INDEX")
    print("Using California CPI for All Urban Consumers")
    print("=" * 80)
    
    # California CPI annual percentage changes (All Urban Consumers)
    # Source: California Department of Industrial Relations [1]
    # Historical data from 1975-2026
    
    ca_cpi_changes = {
        1976: 0.052,  # 5.2% - calculated from CPI index change
        1977: 0.080,  # 8.0%
        1978: 0.089,  # 8.9%
        1979: 0.088,  # 8.8%
        1980: 0.151,  # 15.1%
        1981: 0.130,  # 13.0%
        1982: 0.071,  # 7.1%
        1983: 0.042,  # 4.2%
        1984: 0.043,  # 4.3%
        1985: 0.040,  # 4.0%
        1986: 0.021,  # 2.1%
        1987: 0.053,  # 5.3%
        1988: 0.043,  # 4.3%
        1989: 0.050,  # 5.0%
        1990: 0.050,  # 5.0%
        1991: 0.044,  # 4.4%
        1992: 0.033,  # 3.3%
        1993: 0.027,  # 2.7%
        1994: 0.016,  # 1.6%
        1995: 0.020,  # 2.0%
        1996: 0.023,  # 2.3%
        1997: 0.034,  # 3.4%
        1998: 0.033,  # 3.3%
        1999: 0.042,  # 4.2%
        2000: 0.045,  # 4.5%
        2001: 0.053,  # 5.3%
        2002: 0.015,  # 1.5%
        2003: 0.018,  # 1.8%
        2004: 0.012,  # 1.2%
        2005: 0.020,  # 2.0%
        2006: 0.033,  # 3.3%
        2007: 0.033,  # 3.3%
        2008: 0.030,  # 3.0%
        2009: 0.008,  # 0.8%
        2010: 0.013,  # 1.3%
        2011: 0.027,  # 2.7%
        2012: 0.027,  # 2.7%
        2013: 0.023,  # 2.3%
        2014: 0.028,  # 2.8%
        2015: 0.026,  # 2.6%
        2016: 0.031,  # 3.1%
        2017: 0.032,  # 3.2%
        2018: 0.040,  # 4.0%
        2019: 0.032,  # 3.2%
        2020: 0.017,  # 1.7%
        2021: 0.034,  # 3.4%
        2022: 0.056,  # 5.6%
        2023: 0.035,  # 3.5%
        2024: 0.028,  # 2.8%
        2025: 0.022,  # 2.2% (estimated)
        2026: 0.020,  # 2.0% (estimated - using 2% cap)
    }
    
    # Build the deflator index
    years = list(range(start_year, end_year + 1))
    
    # Calculate Prop 13 allowed increase (lesser of CPI or 2%)
    prop13_allowed_increase = {}
    
    for year in years:
        if year == start_year:
            prop13_allowed_increase[year] = 0.0  # Base year - no increase
        else:
            cpi_change = ca_cpi_changes.get(year, 0.02)  # Default to 2% if missing
            # Prop 13 cap: LESSER of CPI or 2%
            prop13_allowed_increase[year] = min(cpi_change, 0.02)
    
    # Create DataFrame
    df = pd.DataFrame({
        'year': years,
        'ca_cpi_change': [ca_cpi_changes.get(y, 0.02) for y in years],
        'prop13_allowed_increase': [prop13_allowed_increase[y] for y in years]
    })
    
    # Calculate cumulative deflator from current year back to each base year
    # This is the factor to DEFLATE current assessed values to base year values
    
    current_year = end_year
    
    for base_year in years:
        deflator = 1.0
        for year in range(base_year + 1, current_year + 1):
            if year in prop13_allowed_increase:
                deflator *= (1 + prop13_allowed_increase[year])
        
        df.loc[df['year'] == base_year, f'deflator_to_{current_year}'] = deflator
    
    # Add cumulative increase from 1975 (Prop 13 base year)
    df['cumulative_from_1975'] = 1.0
    for i in range(1, len(df)):
        df.loc[i, 'cumulative_from_1975'] = (
            df.loc[i-1, 'cumulative_from_1975'] * 
            (1 + df.loc[i, 'prop13_allowed_increase'])
        )
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    
    print(f"\n✅ Prop 13 deflator index saved to: {output_file}")
    print(f"   Years covered: {start_year} to {end_year}")
    print(f"\n📊 Sample of Prop 13 allowed increases:")
    print(df[['year', 'ca_cpi_change', 'prop13_allowed_increase']].tail(10).to_string(index=False))
    
    print(f"\n📈 Key Statistics:")
    years_capped = (df['ca_cpi_change'] > 0.02).sum()
    print(f"   Years where CPI exceeded 2% cap: {years_capped} out of {len(df)-1}")
    print(f"   Average Prop 13 increase: {df['prop13_allowed_increase'].mean()*100:.2f}%")
    print(f"   Cumulative increase 1975-{end_year}: {(df['cumulative_from_1975'].iloc[-1]-1)*100:.1f}%")
    
    return df


def load_or_create_deflator_index(deflator_file='prop13_deflator_index.csv',
                                   force_rebuild=False):
    """
    Load existing deflator index or create new one if it doesn't exist
    
    Args:
        deflator_file: Path to deflator index CSV
        force_rebuild: If True, rebuild even if file exists
    
    Returns:
        DataFrame with deflator index
    """
    import os
    
    if os.path.exists(deflator_file) and not force_rebuild:
        print(f"📂 Loading existing Prop 13 deflator index from: {deflator_file}")
        df = pd.read_csv(deflator_file)
        print(f"✅ Loaded deflator index with {len(df)} years")
        return df
    else:
        print(f"🔨 Building new Prop 13 deflator index...")
        return build_prop13_deflator_index(output_file=deflator_file)


def deflate_assessed_values_with_cpi(df, deflator_df, current_year=2026):
    """
    Deflate current assessed values to base year using actual Prop 13 rules
    
    Args:
        df: Main property DataFrame with sale_year column
        deflator_df: Prop 13 deflator index DataFrame
        current_year: Current year for deflation calculations
    
    Returns:
        DataFrame with deflated assessed values
    """
    
    print(f"\n🔄 Deflating assessed values using Prop 13 CPI rules...")
    print(f"   Current year: {current_year}")
    
    # Fix type mismatch before merge
    df['sale_year'] = df['sale_year'].astype('Int64')
    deflator_df['year'] = deflator_df['year'].astype(int)
    
    # Merge deflator data
    df = df.merge(
        deflator_df[['year', f'deflator_to_{current_year}']],
        left_on='sale_year',
        right_on='year',
        how='left'
    )
    
    # Rename for clarity
    df.rename(columns={f'deflator_to_{current_year}': 'prop13_deflator'}, inplace=True)
    
    # Deflate assessed values
    has_sale = (
        df['sale_year'].notna() & 
        df['prop13_deflator'].notna()
    )
    
    df.loc[has_sale, 'deflated_assessed_land'] = (
        df.loc[has_sale, 'VAL_ASSD_LAND'] / df.loc[has_sale, 'prop13_deflator']
    )
    
    df.loc[has_sale, 'deflated_assessed_imprv'] = (
        df.loc[has_sale, 'VAL_ASSD_IMPRV'] / df.loc[has_sale, 'prop13_deflator']
    )
    
    df.loc[has_sale, 'deflated_assessed_total'] = (
        df.loc[has_sale, 'VAL_ASSD'] / df.loc[has_sale, 'prop13_deflator']
    )
    
    # Clean up merge columns
    df.drop('year', axis=1, errors='ignore', inplace=True)
    
    deflated_count = has_sale.sum()
    print(f"✅ Deflated {deflated_count:,} properties to base year values")
    
    # Show example
    example = df[has_sale & (df['years_since_sale'] > 5)].head(1)
    if len(example) > 0:
        ex = example.iloc[0]
        print(f"\n📋 Example Deflation:")
        print(f"   Sale year: {ex['sale_year']:.0f}")
        print(f"   Years of Prop 13 inflation: {current_year - ex['sale_year']:.0f}")
        print(f"   Cumulative Prop 13 factor: {ex['prop13_deflator']:.3f}x")
        print(f"   Current assessed: ${ex['VAL_ASSD']:,.0f}")
        print(f"   Deflated to base year: ${ex['deflated_assessed_total']:,.0f}")
        print(f"   Prop 13 inflation removed: ${ex['VAL_ASSD'] - ex['deflated_assessed_total']:,.0f}")
    
    print()
    
    return df


class SacramentoPropertyValuator:
    """
    Estimates true market values by:
    1. Deflating current assessed values back to sale date (removes Prop 13 inflation)
    2. Using recent sales to establish current market rates
    3. Applying those rates to all properties based on H3 spatial proximity
    
    Under Proposition 13, assessed values can only increase by 2% per year
    (or CPI, whichever is lower) until a change in ownership occurs [1][5].
    This creates significant distortions between assessed and market values.
    """
    
    def __init__(self, filepath, current_year=2026):
        self.filepath = filepath
        self.current_year = current_year
        self.df = None
        self.comps = None
        
    def load_data(self):
        """Load and prepare parcel data"""
        print("=" * 80)
        print("🏠 SACRAMENTO PROPERTY VALUATION ENGINE")
        print(f"   Current Year: {self.current_year}")
        print("   Accounting for Proposition 13 Assessment Caps")
        print("=" * 80)
        print(f"\n📂 Loading data from: {self.filepath}")
        
        self.df = pd.read_csv(self.filepath, low_memory=False)
        print(f"✅ Loaded {len(self.df):,} parcels")
        
        # Convert numeric fields
        numeric_fields = [
            'VAL_ASSD', 'VAL_ASSD_LAND', 'VAL_ASSD_IMPRV', 'VAL_TRANSFER',
            'LIVING_SQFT', 'BUILDING_SQFT', 'LOT_SIZE_AREA', 'YR_BLT', 
            'BEDROOMS', 'TOTAL_BATHS', 'LATITUDE', 'LONGITUDE', 
            'STORIES_NUMBER', 'UNITS_NUMBER'
        ]
        
        # Parse date fields
        date_fields = [
            'LAST_SALE_DATE_TRANSFER', 'DATE_TRANSFER',
            'LAST_MARKET_DATE_TRANSFER', 'ASMT_RCDRS_DATE_TRANSFER',
            'PRIOR_SALE_DATE_TRANSFER', 'PRIOR_MARKET_SALE_DATE_TRANSFER',  # ADD THESE
        ]
        
        # Replace the date parsing loop with this:
        for field in date_fields:
            if field in self.df.columns:
                col = self.df[field]
                # Handle YYYYMMDD stored as float (e.g. 20140925.0)
                non_null = col.dropna()
                if len(non_null) > 0 and pd.api.types.is_float_dtype(col):
                    self.df[field] = pd.to_datetime(
                        col.where(col.isna(), col.astype('Int64').astype(str)),
                        format='%Y%m%d',
                        errors='coerce'
                    )
                else:
                    self.df[field] = pd.to_datetime(col, errors='coerce')
            

        
        for field in date_fields:
            if field in self.df.columns:
                self.df[field] = pd.to_datetime(self.df[field], errors='coerce')
        
        # Build best sale date: prefer LAST_MARKET_DATE_TRANSFER, fall back to others
        self.df['sale_date'] = (
            self.df['LAST_MARKET_DATE_TRANSFER']
            .fillna(self.df.get('PRIOR_MARKET_SALE_DATE_TRANSFER'))
            .fillna(self.df.get('DATE_TRANSFER'))
            .fillna(self.df.get('LAST_SALE_DATE_TRANSFER'))
            .fillna(self.df.get('ASMT_RCDRS_DATE_TRANSFER'))
        )
        
        self.df['sale_price'] = self.df['VAL_TRANSFER']
        
        price_cols = ['VAL_TRANSFER', 'ASMT_VAL_TRANSFER', 
              'PRIOR_SALE_RAW_VAL_TRANSFER', 'PRIOR_SALE_VAL_TRANSFER']
        available_price_cols = [c for c in price_cols if c in self.df.columns]
        
        self.df['sale_price'] = np.nan
        for col in reversed(available_price_cols):  # reversed so first col wins
            valid = self.df[col].notna() & (self.df[col] > 0)
            self.df.loc[valid, 'sale_price'] = self.df.loc[valid, col]
        
        # Calculate time metrics with CORRECT current year
        self.df['sale_year'] = self.df['sale_date'].dt.year
        self.df['years_since_sale'] = self.current_year - self.df['sale_year']
        
        # Property age with CORRECT current year
        self.df['property_age'] = self.current_year - self.df['YR_BLT']
        
        # Determine property type based on available data
        self.df['has_improvements'] = (
            (self.df['VAL_ASSD_IMPRV'].notna()) & 
            (self.df['VAL_ASSD_IMPRV'] > 0)
        )
        
        self.df['is_vacant_land'] = (
            (~self.df['has_improvements']) | 
            (self.df['LIVING_SQFT'].isna()) |
            (self.df['LIVING_SQFT'] == 0)
        )
        
        # Use appropriate square footage based on property type
        # For residential with living space, use that
        # For commercial/other, use building sqft
        # For vacant land, just lot size
        self.df['primary_sqft'] = self.df['LIVING_SQFT'].fillna(
            self.df['BUILDING_SQFT']
        )
        
        print(f"✅ Data preparation complete\n")
        
        # Data quality check
        self._check_data_quality()
        
        return self
    
    
    def diagnose_sale_data(self):
        """Temporary diagnostic to understand why deflation merge is failing"""
        print("\n" + "="*60)
        print("🔍 DIAGNOSTIC: Sale Data Investigation")
        print("="*60)
        
        # Check sale_date and sale_year
        print(f"\nsale_date non-null: {self.df['sale_date'].notna().sum():,}")
        print(f"sale_year non-null: {self.df['sale_year'].notna().sum():,}")
        print(f"sale_year dtype: {self.df['sale_year'].dtype}")
        
        # Show sample values
        sample = self.df[self.df['sale_year'].notna()]['sale_year'].head(10)
        print(f"\nSample sale_year values:\n{sample.tolist()}")
        
        # Show value range
        print(f"\nsale_year min: {self.df['sale_year'].min()}")
        print(f"sale_year max: {self.df['sale_year'].max()}")
        
        # Show unique count
        print(f"Unique sale years: {self.df['sale_year'].nunique()}")
        print(f"Value counts (top 10):\n{self.df['sale_year'].value_counts().head(10)}")
        
        # Check the source date columns
        print("\n--- Source Date Column Diagnostics ---")
        date_cols = ['LAST_MARKET_DATE_TRANSFER', 'DATE_TRANSFER', 
                     'LAST_SALE_DATE_TRANSFER', 'sale_date']
        for col in date_cols:
            if col in self.df.columns:
                non_null = self.df[col].notna().sum()
                print(f"{col}: {non_null:,} non-null, dtype={self.df[col].dtype}")
                if non_null > 0:
                    sample_val = self.df[col].dropna().iloc[0]
                    print(f"  Sample value: {sample_val!r}")
        
        # Check VAL_TRANSFER
        print(f"\nVAL_TRANSFER non-null: {self.df['VAL_TRANSFER'].notna().sum():,}" 
              if 'VAL_TRANSFER' in self.df.columns else "\nVAL_TRANSFER: NOT FOUND")
        if 'VAL_TRANSFER' in self.df.columns:
            print(f"VAL_TRANSFER > 0: {(self.df['VAL_TRANSFER'] > 0).sum():,}")
            print(f"Sample values: {self.df['VAL_TRANSFER'].dropna().head(5).tolist()}")
        
        # Check deflator index
        print(f"\n--- Deflator Index Sample ---")
        if hasattr(self, 'deflator_df'):
            print(f"deflator_df year dtype: {self.deflator_df['year'].dtype}")
            print(f"deflator_df years: {self.deflator_df['year'].tolist()[:5]} ... {self.deflator_df['year'].tolist()[-5:]}")
        
        print("="*60 + "\n")
        return self
    
    def _check_data_quality(self):
        """Check quality of assessed value data"""
        print("📊 Property Type Distribution:")
        has_imprv = self.df['has_improvements'].sum()
        is_vacant = self.df['is_vacant_land'].sum()
        
        print(f"   Properties with improvements: {has_imprv:,} " +
              f"({has_imprv/len(self.df)*100:.1f}%)")
        print(f"   Vacant land parcels: {is_vacant:,} " +
              f"({is_vacant/len(self.df)*100:.1f}%)")
        print(f"   With LIVING_SQFT: {self.df['LIVING_SQFT'].notna().sum():,}")
        print(f"   With BUILDING_SQFT: {self.df['BUILDING_SQFT'].notna().sum():,}")
        
        print("\n📊 Assessed Value Data Quality:")
        for field in ['VAL_ASSD_LAND', 'VAL_ASSD_IMPRV', 'VAL_ASSD']:
            count = self.df[field].notna().sum()
            pct = count / len(self.df) * 100
            print(f"   {field} populated: {count:,} ({pct:.1f}%)")
        
        # Check if land + improvement = total
        has_all = (
            self.df['VAL_ASSD_LAND'].notna() & 
            self.df['VAL_ASSD_IMPRV'].notna() & 
            self.df['VAL_ASSD'].notna()
        )
        
        if has_all.sum() > 0:
            calculated = (self.df.loc[has_all, 'VAL_ASSD_LAND'] + 
                         self.df.loc[has_all, 'VAL_ASSD_IMPRV'])
            actual = self.df.loc[has_all, 'VAL_ASSD']
            matches = np.isclose(calculated, actual, rtol=0.01)
            match_count = matches.sum()
            print(f"   Land + Improvement = Total: {match_count:,}/" +
                  f"{has_all.sum():,} ({match_count/has_all.sum()*100:.1f}%)")
        
        print()
        
    
    def deflate_assessed_values_to_base_year(self):
        """
        UPDATED: Deflate current assessed values using actual Prop 13 CPI rules
        """
        print("🔄 Deflating assessed values using Prop 13 CPI caps...")
        
        # Load or create deflator index
        self.deflator_df = load_or_create_deflator_index()
        
        # Apply deflation
        self.df = deflate_assessed_values_with_cpi(
            self.df, 
            self.deflator_df, 
            current_year=self.current_year
        )
        
        return self
    
    def calculate_sale_assessment_ratios(self):
        """
        Calculate what percentage of sale price went to land vs improvements
        at the TIME OF SALE (using deflated assessed values)
        
        This is the key step that allows us to properly apportion value.
        """
        print("📊 Calculating land/improvement splits from sale data...")
        
        has_valid_data = (
            (self.df['sale_price'].notna()) &
            (self.df['sale_price'] > 0) &
            (self.df['deflated_assessed_total'].notna()) &
            (self.df['deflated_assessed_total'] > 0)
        )
        
        # Calculate the proportion of assessed value that is land vs improvement
        # These proportions should roughly match the market's valuation
        self.df.loc[has_valid_data, 'land_proportion_of_assessed'] = (
            self.df.loc[has_valid_data, 'deflated_assessed_land'] / 
            self.df.loc[has_valid_data, 'deflated_assessed_total']
        ).clip(0, 1)
        
        self.df.loc[has_valid_data, 'imprv_proportion_of_assessed'] = (
            self.df.loc[has_valid_data, 'deflated_assessed_imprv'] / 
            self.df.loc[has_valid_data, 'deflated_assessed_total']
        ).clip(0, 1)
        
        # Apply these proportions to the ACTUAL sale price
        # This gives us the implied land and improvement values at sale
        self.df.loc[has_valid_data, 'land_value_at_sale'] = (
            self.df.loc[has_valid_data, 'sale_price'] * 
            self.df.loc[has_valid_data, 'land_proportion_of_assessed']
        )
        
        self.df.loc[has_valid_data, 'improvement_value_at_sale'] = (
            self.df.loc[has_valid_data, 'sale_price'] * 
            self.df.loc[has_valid_data, 'imprv_proportion_of_assessed']
        )
        
        # Calculate per-unit values at time of sale
        has_lot = has_valid_data & (self.df['LOT_SIZE_AREA'] > 0)
        self.df.loc[has_lot, 'land_value_per_sqft_at_sale'] = (
            self.df.loc[has_lot, 'land_value_at_sale'] / 
            self.df.loc[has_lot, 'LOT_SIZE_AREA']
        )
        
        has_improvements = (
            has_valid_data & 
            (self.df['primary_sqft'] > 0) & 
            (~self.df['is_vacant_land'])
        )
        self.df.loc[has_improvements, 'improvement_value_per_sqft_at_sale'] = (
            self.df.loc[has_improvements, 'improvement_value_at_sale'] / 
            self.df.loc[has_improvements, 'primary_sqft']
        )
        
        calculated = has_valid_data.sum()
        print(f"✅ Calculated sale ratios for {calculated:,} properties\n")
        
        # Summary statistics
        if calculated > 0:
            print(f"📊 Land/Improvement Split Summary:")
            median_land_pct = self.df.loc[has_valid_data, 'land_proportion_of_assessed'].median() * 100
            median_imprv_pct = self.df.loc[has_valid_data, 'imprv_proportion_of_assessed'].median() * 100
            print(f"   Median land proportion: {median_land_pct:.1f}%")
            print(f"   Median improvement proportion: {median_imprv_pct:.1f}%")
            
            if has_lot.sum() > 0:
                median_land_sqft = self.df.loc[has_lot, 'land_value_per_sqft_at_sale'].median()
                print(f"   Median land value per sqft: ${median_land_sqft:.2f}")
            
            if has_improvements.sum() > 0:
                median_imprv_sqft = self.df.loc[has_improvements, 'improvement_value_per_sqft_at_sale'].median()
                print(f"   Median improvement value per sqft: ${median_imprv_sqft:.2f}")
            
            print()
        
        return self
    
    def identify_recent_comparable_sales(self, lookback_years=3, 
                                        min_sale_price=50000, 
                                        max_sale_price=10000000):
        """
        Identify recent sales that represent CURRENT market values
        
        These will be used to establish current per-sqft rates for
        land and improvements in each location
        
        Args:
            lookback_years: Only use sales from last N years
            min_sale_price: Filter out suspiciously low sales
            max_sale_price: Filter out extreme outliers
        """
        print(f"🔍 Identifying recent comparable sales...")
        print(f"   Lookback period: {lookback_years} years")
        
        cutoff_year = self.current_year - lookback_years
        
        # Filter for recent, valid sales WITH calculated land/improvement values
        comp_filters = (
            (self.df['sale_year'] >= cutoff_year) &
            (self.df['sale_price'].notna()) &
            (self.df['sale_price'] >= min_sale_price) &
            (self.df['sale_price'] <= max_sale_price) &
            (self.df['land_value_at_sale'].notna()) &
            (self.df['land_value_at_sale'] > 0) &
            (self.df['LOT_SIZE_AREA'].notna()) &
            (self.df['LOT_SIZE_AREA'] > 0) &
            (self.df['land_value_per_sqft_at_sale'].notna())
        )
        
        # Additional filters for improved properties
        improved_filters = comp_filters & (
            (self.df['improvement_value_at_sale'].notna()) &
            (self.df['improvement_value_at_sale'] > 0) &
            (self.df['primary_sqft'].notna()) &
            (self.df['primary_sqft'] > 400) &
            (self.df['primary_sqft'] < 50000) &
            (self.df['improvement_value_per_sqft_at_sale'].notna()) &
            (self.df['improvement_value_per_sqft_at_sale'] >= 25) &
            (self.df['improvement_value_per_sqft_at_sale'] <= 1500)
        )
        
        # Vacant land filters
        vacant_filters = comp_filters & (
            (self.df['is_vacant_land']) |
            (self.df['improvement_value_at_sale'].isna()) |
            (self.df['improvement_value_at_sale'] == 0)
        )
        
        self.comps = self.df[improved_filters | vacant_filters].copy()
        
        print(f"✅ Found {len(self.comps):,} valid recent comparable sales\n")
        
        improved_comps = self.comps[~self.comps['is_vacant_land']]
        vacant_comps = self.comps[self.comps['is_vacant_land']]
        
        print(f"📊 Comparable Sales Breakdown:")
        print(f"   Improved properties: {len(improved_comps):,}")
        print(f"   Vacant land: {len(vacant_comps):,}")
        
        if len(self.comps) > 0:
            date_range_start = self.comps['sale_date'].min().date()
            date_range_end = self.comps['sale_date'].max().date()
            print(f"   Date range: {date_range_start} to {date_range_end}")
        
        if len(improved_comps) > 0:
            print(f"\n   Improved Properties:")
            print(f"     Median sale price: ${improved_comps['sale_price'].median():,.0f}")
            print(f"     Median land $/sqft: ${improved_comps['land_value_per_sqft_at_sale'].median():.2f}")
            print(f"     Median improvement $/sqft: ${improved_comps['improvement_value_per_sqft_at_sale'].median():.2f}")
        
        if len(vacant_comps) > 0:
            print(f"\n   Vacant Land:")
            print(f"     Median sale price: ${vacant_comps['sale_price'].median():,.0f}")
            print(f"     Median land $/sqft: ${vacant_comps['land_value_per_sqft_at_sale'].median():.2f}")
        
                
        # Remove comps with implausible land $/sqft (keep between $1 and $500 for vacant land)
        before = len(self.comps)
        land_rate_ok = (
            self.comps['land_value_per_sqft_at_sale'].isna() |  # keep if not yet calculated
            (
                (self.comps['land_value_per_sqft_at_sale'] >= 1) &
                (self.comps['land_value_per_sqft_at_sale'] <= 500)
            )
        )
        self.comps = self.comps[land_rate_ok].copy()
        print(f"   Removed {before - len(self.comps):,} comps with implausible land $/sqft (outside $1-$500)")
        
        
        # Only use comps where sale price is in a reasonable range for the lot size
        # i.e. implied $/sqft must be between $1-$500 for vacant, $25-$500 for improved
        # This is already handled above, but also filter by USE_CODE
        if 'USE_CODE_STD_LPS' in self.df.columns:
            # Exclude industrial, utility, special use from comps
            exclude_use_codes = [
                4000, 4001, 4002,  # industrial
                5000, 5001,        # utilities  
                8000, 8001, 8009,  # misc/waste/unusable
                9000, 9001,        # exempt
            ]
            before = len(self.comps)
            self.comps = self.comps[
                ~self.comps['USE_CODE_STD_LPS'].isin(exclude_use_codes)
            ].copy()
            print(f"   Removed {before - len(self.comps):,} comps with industrial/utility/waste use codes")
    
        print()

        return self
    
    def calculate_current_market_rates_by_h3(self, 
                                             initial_resolution=11,
                                             min_resolution=7,
                                             min_comps_required=5):
        """
        Calculate current market rates ($/sqft for land and improvements)
        using H3 hexagons with cascading fallback
        
        Strategy:
        1. Start at fine resolution (H3-11, sub-block level)
        2. If insufficient recent comps, expand to larger hexagons
        3. Continue until min_comps_required is met
        4. Track which resolution was used for transparency
        
        Args:
            initial_resolution: Starting H3 resolution (11 = sub-block)
            min_resolution: Minimum H3 resolution (7 = large area)
            min_comps_required: Minimum recent sales needed
        """
        print(f"🗺️  Calculating current market rates by H3 hexagon...")
        print(f"   Initial resolution: H3-{initial_resolution}")
        print(f"   Minimum required comps: {min_comps_required}")
        print(f"   Will cascade down to H3-{min_resolution} if needed\n")
        
        # Initialize tracking columns
        self.df['current_land_value_per_sqft'] = np.nan
        self.df['current_improvement_value_per_sqft'] = np.nan
        self.df['comp_count'] = 0
        self.df['h3_resolution_used'] = np.nan
        self.df['estimation_method'] = 'none'
        
        total_parcels = len(self.df)
        parcels_with_rates = 0
        
        resolution_usage = {}
        
        # Process each H3 resolution from fine to coarse
        for resolution in range(initial_resolution, min_resolution - 1, -1):
            h3_field = f'H3_INT_{resolution}'
            
            if h3_field not in self.df.columns:
                print(f"   ⚠️  H3-{resolution} field not found, skipping...")
                continue
            
            print(f"   Processing H3-{resolution}...")
            
            # Calculate market rates from recent comps for this resolution
            # Separate for improved vs vacant land
            
            # For improved properties
            improved_comps = self.comps[
                (~self.comps['is_vacant_land']) &
                (self.comps['improvement_value_per_sqft_at_sale'].notna())
            ].copy()
            
            if len(improved_comps) > 0:
                improved_stats = improved_comps.groupby(h3_field).agg({
                    'land_value_per_sqft_at_sale': ['median', 'mean', 'count'],
                    'improvement_value_per_sqft_at_sale': ['median', 'mean'],
                    'sale_price': 'median'
                }).reset_index()
                
                improved_stats.columns = ['_'.join(col).strip('_') for col in improved_stats.columns.values]
                improved_stats.rename(columns={
                    h3_field: h3_field,
                    'land_value_per_sqft_at_sale_median': 'land_rate_improved',
                    'improvement_value_per_sqft_at_sale_median': 'imprv_rate_improved',
                    'land_value_per_sqft_at_sale_count': 'comp_count_improved'
                }, inplace=True)
                
                # Merge to main df
                self.df = self.df.merge(
                    improved_stats[[h3_field, 'land_rate_improved', 
                                   'imprv_rate_improved', 'comp_count_improved']], 
                    on=h3_field, how='left'
                )
            else:
                self.df['comp_count_improved'] = 0

            # For vacant land
            vacant_comps = self.comps[
                (self.comps['is_vacant_land']) &
                (self.comps['land_value_per_sqft_at_sale'].notna())
            ].copy()
            
            if len(vacant_comps) > 0:
                vacant_stats = vacant_comps.groupby(h3_field).agg({
                    'land_value_per_sqft_at_sale': ['median', 'mean', 'count'],
                    'sale_price': 'median'
                }).reset_index()
                
                vacant_stats.columns = ['_'.join(col).strip('_') for col in vacant_stats.columns.values]
                vacant_stats.rename(columns={
                    h3_field: h3_field,
                    'land_value_per_sqft_at_sale_median': 'land_rate_vacant',
                    'land_value_per_sqft_at_sale_count': 'comp_count_vacant'
                }, inplace=True)
                
                # Merge to main df
                self.df = self.df.merge(
                    vacant_stats[[h3_field, 'land_rate_vacant', 'comp_count_vacant']], 
                    on=h3_field, how='left'
                )
            else:
                self.df['comp_count_vacant'] = 0
            
            # Apply rates where we don't have them yet AND meet minimum comp threshold
            
            # For improved properties
            needs_rates = (
                (self.df['current_land_value_per_sqft'].isna()) &
                (~self.df['is_vacant_land']) &
                (self.df['comp_count_improved'].fillna(0) >= min_comps_required)
            )
            
            if needs_rates.sum() > 0:
                self.df.loc[needs_rates, 'current_land_value_per_sqft'] = (
                    self.df.loc[needs_rates, 'land_rate_improved']
                )
                self.df.loc[needs_rates, 'current_improvement_value_per_sqft'] = (
                    self.df.loc[needs_rates, 'imprv_rate_improved']
                )
                self.df.loc[needs_rates, 'comp_count'] = (
                    self.df.loc[needs_rates, 'comp_count_improved']
                )
                self.df.loc[needs_rates, 'h3_resolution_used'] = resolution
                self.df.loc[needs_rates, 'estimation_method'] = f'h3_{resolution}_improved'
                
                parcels_with_rates += needs_rates.sum()
                resolution_usage[f'H3-{resolution}_improved'] = needs_rates.sum()
            
            # For vacant land
            needs_rates_vacant = (
                (self.df['current_land_value_per_sqft'].isna()) &
                (self.df['is_vacant_land']) &
                (self.df['comp_count_vacant'].fillna(0) >= min_comps_required)
            )
            
            if needs_rates_vacant.sum() > 0:
                self.df.loc[needs_rates_vacant, 'current_land_value_per_sqft'] = (
                    self.df.loc[needs_rates_vacant, 'land_rate_vacant']
                )
                # Vacant land has no improvement value
                self.df.loc[needs_rates_vacant, 'current_improvement_value_per_sqft'] = 0
                self.df.loc[needs_rates_vacant, 'comp_count'] = (
                    self.df.loc[needs_rates_vacant, 'comp_count_vacant']
                )
                self.df.loc[needs_rates_vacant, 'h3_resolution_used'] = resolution
                self.df.loc[needs_rates_vacant, 'estimation_method'] = f'h3_{resolution}_vacant'
                
                parcels_with_rates += needs_rates_vacant.sum()
                resolution_usage[f'H3-{resolution}_vacant'] = needs_rates_vacant.sum()
            
            # Clean up temporary columns
            temp_cols = [c for c in self.df.columns if c.startswith((
                'land_rate_', 'imprv_rate_', 'comp_count_improved', 'comp_count_vacant'
            ))]
            self.df.drop(temp_cols, axis=1, inplace=True)
            
            current_total = needs_rates.sum() + needs_rates_vacant.sum()
            print(f"     Assigned rates: {current_total:,} parcels at this resolution")
            print(f"     Cumulative: {parcels_with_rates:,}/{total_parcels:,} " +
                  f"({parcels_with_rates/total_parcels*100:.1f}%)")
        
        # Final fallback for any remaining parcels - use countywide median from recent sales
        still_missing = self.df['current_land_value_per_sqft'].isna()
        if still_missing.sum() > 0:
            print(f"\n   ⚠️  {still_missing.sum():,} parcels still need market rates")
            print(f"     Applying countywide median from recent sales as final fallback...")
            
            # Separate countywide medians for improved vs vacant
            improved_county = self.comps[~self.comps['is_vacant_land']]
            vacant_county = self.comps[self.comps['is_vacant_land']]
            
            if len(improved_county) > 0:
                county_land_improved = improved_county['land_value_per_sqft_at_sale'].median()
                county_imprv_improved = improved_county['improvement_value_per_sqft_at_sale'].median()
                
                missing_improved = still_missing & (~self.df['is_vacant_land'])
                if missing_improved.sum() > 0:
                    self.df.loc[missing_improved, 'current_land_value_per_sqft'] = county_land_improved
                    self.df.loc[missing_improved, 'current_improvement_value_per_sqft'] = county_imprv_improved
                    self.df.loc[missing_improved, 'comp_count'] = 0
                    self.df.loc[missing_improved, 'h3_resolution_used'] = 0
                    self.df.loc[missing_improved, 'estimation_method'] = 'countywide_improved'
                    
                    resolution_usage['countywide_improved'] = missing_improved.sum()
                    print(f"       Improved properties: {missing_improved.sum():,}")
                    print(f"         Land rate: ${county_land_improved:.2f}/sqft")
                    print(f"         Improvement rate: ${county_imprv_improved:.2f}/sqft")
            
            if len(vacant_county) > 0:
                county_land_vacant = vacant_county['land_value_per_sqft_at_sale'].median()
                
                missing_vacant = still_missing & (self.df['is_vacant_land'])
                if missing_vacant.sum() > 0:
                    self.df.loc[missing_vacant, 'current_land_value_per_sqft'] = county_land_vacant
                    self.df.loc[missing_vacant, 'current_improvement_value_per_sqft'] = 0
                    self.df.loc[missing_vacant, 'comp_count'] = 0
                    self.df.loc[missing_vacant, 'h3_resolution_used'] = 0
                    self.df.loc[missing_vacant, 'estimation_method'] = 'countywide_vacant'
                    
                    resolution_usage['countywide_vacant'] = missing_vacant.sum()
                    print(f"       Vacant land: {missing_vacant.sum():,}")
                    print(f"         Land rate: ${county_land_vacant:.2f}/sqft")
        
        total_with_rates = self.df['current_land_value_per_sqft'].notna().sum()
        print(f"\n✅ Market rates calculated for {total_with_rates:,} parcels\n")
        
        print("📊 Estimation Method Distribution:")
        for method, count in sorted(resolution_usage.items(), 
                                    key=lambda x: x[1], reverse=True):
            pct = (count / total_parcels) * 100
            print(f"   {method}: {count:,} ({pct:.1f}%)")
        
        print()
        
        return self
    
    def estimate_current_market_values(self):
        """
        Estimate current market values by applying current market rates
        to property characteristics
        """
        print("💰 Estimating current market values...")
        
        # Estimate land value using current market rate
        has_lot = (
            (self.df['LOT_SIZE_AREA'].notna()) &
            (self.df['LOT_SIZE_AREA'] > 0) &
            (self.df['current_land_value_per_sqft'].notna())
        )
        
        self.df.loc[has_lot, 'estimated_land_value'] = (
            self.df.loc[has_lot, 'LOT_SIZE_AREA'] * 
            self.df.loc[has_lot, 'current_land_value_per_sqft']
        )
        
        # Estimate improvement value (only for improved properties)
        has_improvements = (
            (self.df['primary_sqft'].notna()) &
            (self.df['primary_sqft'] > 0) &
            (~self.df['is_vacant_land']) &
            (self.df['current_improvement_value_per_sqft'].notna())
        )
        
        self.df.loc[has_improvements, 'estimated_improvement_value'] = (
            self.df.loc[has_improvements, 'primary_sqft'] * 
            self.df.loc[has_improvements, 'current_improvement_value_per_sqft']
        )
        
        # For vacant land, improvement value is 0
        self.df.loc[self.df['is_vacant_land'], 'estimated_improvement_value'] = 0
        
        # Total estimated market value
        self.df['estimated_total_market_value'] = (
            self.df['estimated_land_value'].fillna(0) + 
            self.df['estimated_improvement_value'].fillna(0)
        )
        
        # Set to NaN if no valid estimate
        no_estimate = (
            (self.df['estimated_land_value'].isna() | (self.df['estimated_land_value'] == 0)) & 
            (self.df['estimated_improvement_value'].isna() | (self.df['estimated_improvement_value'] == 0))
        )
        self.df.loc[no_estimate, 'estimated_total_market_value'] = np.nan
        
        valid = self.df['estimated_total_market_value'].notna()
        
        print(f"✅ Estimated market values for {valid.sum():,} parcels")
        print(f"\n📊 Estimated Values Summary:")
        
        has_land_est = self.df['estimated_land_value'] > 0
        if has_land_est.sum() > 0:
            median_land = self.df.loc[has_land_est, 'estimated_land_value'].median()
            print(f"   Land value - Median: ${median_land:,.0f}")
        
        has_imprv_est = self.df['estimated_improvement_value'] > 0
        if has_imprv_est.sum() > 0:
            median_imprv = self.df.loc[has_imprv_est, 'estimated_improvement_value'].median()
            print(f"   Improvement value - Median: ${median_imprv:,.0f}")
        
        if valid.sum() > 0:
            median_total = self.df.loc[valid, 'estimated_total_market_value'].median()
            print(f"   Total market value - Median: ${median_total:,.0f}")
        
        # Sanity cap: estimated value shouldn't exceed 5x assessed value
        # Prop 13 math: 2%/year for 51 years = ~2.8x max suppression
        MAX_RATIO = 5.0
        has_both = (
            self.df['estimated_total_market_value'].notna() & 
            self.df['VAL_ASSD'].notna() & 
            (self.df['VAL_ASSD'] > 0)
        )
        ratio = self.df.loc[has_both, 'estimated_total_market_value'] / self.df.loc[has_both, 'VAL_ASSD']
        capped = has_both & (ratio > MAX_RATIO)
        print(f"⚠️  Capping {capped.sum():,} estimates exceeding {MAX_RATIO}x assessed value")
        self.df.loc[capped, 'estimated_total_market_value'] = np.nan
        self.df.loc[capped, 'estimated_land_value'] = np.nan
        self.df.loc[capped, 'estimation_method'] = 'excluded_implausible'
        
        print()
        
        return self
    
    def calculate_equity_metrics(self):
        """
        Calculate property equity and Prop 13 benefits
        """
        print("📈 Calculating equity metrics...")
        
        # Hidden equity from Prop 13 (market value - assessed value)
        self.df['prop13_hidden_equity'] = (
            self.df['estimated_total_market_value'] - self.df['VAL_ASSD']
        ).clip(lower=0)
        
        # Hidden equity percentage
        self.df['prop13_benefit_pct'] = np.where(
            self.df['estimated_total_market_value'] > 0,
            (self.df['prop13_hidden_equity'] / self.df['estimated_total_market_value']) * 100,
            np.nan
        )
        self.df['prop13_benefit_pct'] = self.df['prop13_benefit_pct'].clip(upper=100)
        
        
        # Annual property tax savings (assuming 1.1% effective tax rate in California)
        # This is the tax they WOULD pay on market value minus what they DO pay on assessed value
        self.df['annual_tax_on_market'] = self.df['estimated_total_market_value'] * 0.011
        self.df['annual_tax_on_assessed'] = self.df['VAL_ASSD'] * 0.011
        self.df['annual_tax_savings'] = (
            self.df['annual_tax_on_market'] - self.df['annual_tax_on_assessed']
        ).clip(lower=0)
        
        # Calculate cumulative tax savings over ownership period
        self.df['cumulative_tax_savings'] = (
            self.df['annual_tax_savings'] * self.df['years_since_sale']
        ).clip(lower=0)
        
        # Equity extraction potential
        # This represents value that could be extracted through sale or refinancing
        self.df['extractable_equity'] = self.df['prop13_hidden_equity']
        
        # Land equity vs improvement equity
        self.df['land_hidden_equity'] = (
            self.df['estimated_land_value'] - self.df['VAL_ASSD_LAND']
        ).clip(lower=0)
        
        self.df['improvement_hidden_equity'] = (
            self.df['estimated_improvement_value'] - self.df['VAL_ASSD_IMPRV'].fillna(0)
        ).clip(lower=0)
        
        # Categorize benefit levels
        self.df['benefit_category'] = pd.cut(
            self.df['prop13_benefit_pct'],
            bins=[0, 10, 25, 50, 100],
            labels=['Minimal (<10%)', 'Low (10-25%)', 'Moderate (25-50%)', 'High (50%+)']
        )
        
        valid = self.df['prop13_hidden_equity'].notna() & (self.df['prop13_hidden_equity'] > 0)
        
        print(f"✅ Calculated equity metrics for {valid.sum():,} parcels\n")
        
        if valid.sum() > 0:
            print("📊 Prop 13 Tax Benefit Summary:")
            print(f"   Median hidden equity: ${self.df.loc[valid, 'prop13_hidden_equity'].median():,.0f}")
            print(f"   Median benefit %: {self.df.loc[valid, 'prop13_benefit_pct'].median():.1f}%")
            print(f"   Median annual tax savings: ${self.df.loc[valid, 'annual_tax_savings'].median():,.0f}")
            print(f"   Total hidden equity: ${self.df.loc[valid, 'prop13_hidden_equity'].sum():,.0f}")
            print(f"   Total annual tax savings: ${self.df.loc[valid, 'annual_tax_savings'].sum():,.0f}")
            
            print(f"\n📊 Distribution by Benefit Category:")
            benefit_dist = self.df['benefit_category'].value_counts().sort_index()
            for category, count in benefit_dist.items():
                pct = (count / len(self.df)) * 100
                print(f"   {category}: {count:,} ({pct:.1f}%)")
        
        print()
        
        return self
    
    def generate_output_file(self, output_filename='sacramento_property_valuations_enhanced.csv'):
        """
        Generate final CSV with all key fields
        """
        print(f"💾 Generating output file: {output_filename}")
        
        # Select output columns
        output_columns = [
            # Identifiers
            'PARCEL_APN',
            'SITE_ADDR',
            'SITE_CITY',
            'SITE_ZIP',
            
            # Location
            'LATITUDE',
            'LONGITUDE',
            'H3_INT_10',
            'H3_INT_11',
            
            # Property characteristics
            'LIVING_SQFT',
            'BUILDING_SQFT',
            'primary_sqft',
            'LOT_SIZE_AREA',
            'YR_BLT',
            'property_age',
            'BEDROOMS',
            'TOTAL_BATHS',
            'is_vacant_land',
            'has_improvements',
            
            # Sale information
            'sale_date',
            'sale_year',
            'sale_price',
            'years_since_sale',
            
            # Assessed values (Prop 13 suppressed)
            'VAL_ASSD_LAND',
            'VAL_ASSD_IMPRV',
            'VAL_ASSD',
            'ASMT_YEAR',
            
            # Deflated assessed values (back to base year)
            'deflated_assessed_land',
            'deflated_assessed_imprv',
            'deflated_assessed_total',
            
            # Sale-time values (for properties that sold)
            'land_value_at_sale',
            'improvement_value_at_sale',
            'land_value_per_sqft_at_sale',
            'improvement_value_per_sqft_at_sale',
            
            # Current market rates (from recent comps)
            'current_land_value_per_sqft',
            'current_improvement_value_per_sqft',
            
            # Estimated real market values
            'estimated_land_value',
            'estimated_improvement_value',
            'estimated_total_market_value',
            
            # Estimation quality indicators
            'comp_count',
            'h3_resolution_used',
            'estimation_method',
            
            # Equity metrics
            'prop13_hidden_equity',
            'land_hidden_equity',
            'improvement_hidden_equity',
            'prop13_benefit_pct',
            'annual_tax_savings',
            'cumulative_tax_savings',
            'extractable_equity',
            'benefit_category',
            
            # Owner information
            'OWNER_OCCUPIED',
            'ASMT_OWNER_OCCUPIED'
        ]
        
        # Filter to only columns that exist
        available_columns = [col for col in output_columns if col in self.df.columns]
        
        # Export
        output_df = self.df[available_columns].copy()
        
        # Round numeric columns for cleaner output
        numeric_cols = output_df.select_dtypes(include=[np.number]).columns
        output_df[numeric_cols] = output_df[numeric_cols].round(2)
        
        output_df.to_csv(output_filename, index=False)
        
        print(f"✅ Output file created with {len(available_columns)} columns")
        print(f"   Total records: {len(output_df):,}")
        
        has_valuation = output_df['estimated_total_market_value'].notna()
        print(f"   Records with valuations: {has_valuation.sum():,} " +
              f"({has_valuation.sum()/len(output_df)*100:.1f}%)")
        
        return self
    
    def generate_summary_report(self):
        """
        Generate comprehensive summary statistics report
        """
        print("\n" + "="*80)
        print("📊 FINAL VALUATION SUMMARY REPORT")
        print("="*80)
        
        has_estimate = self.df['estimated_total_market_value'].notna()
        
        print(f"\n📈 Overall Statistics:")
        print(f"   Total parcels analyzed: {len(self.df):,}")
        print(f"   Parcels with valuations: {has_estimate.sum():,} " +
              f"({has_estimate.sum()/len(self.df)*100:.1f}%)")
        print(f"   Vacant land parcels: {self.df['is_vacant_land'].sum():,}")
        print(f"   Improved parcels: {self.df['has_improvements'].sum():,}")
        
        if has_estimate.sum() > 0:
            print(f"\n💰 Valuation Summary:")
            total_assessed = self.df.loc[has_estimate, 'VAL_ASSD'].sum()
            total_market = self.df.loc[has_estimate, 'estimated_total_market_value'].sum()
            total_hidden = self.df.loc[has_estimate, 'prop13_hidden_equity'].sum()
            total_tax_savings = self.df.loc[has_estimate, 'annual_tax_savings'].sum()
            
            print(f"   Total assessed value: ${total_assessed:,.0f}")
            print(f"   Total estimated market value: ${total_market:,.0f}")
            print(f"   Total hidden equity (Prop 13): ${total_hidden:,.0f}")
            print(f"   Total annual tax savings: ${total_tax_savings:,.0f}")
            print(f"   Overall assessment ratio: {(total_assessed/total_market)*100:.1f}%")
            
            print(f"\n📊 Median Values:")
            print(f"   Assessed value: ${self.df.loc[has_estimate, 'VAL_ASSD'].median():,.0f}")
            print(f"   Estimated market value: ${self.df.loc[has_estimate, 'estimated_total_market_value'].median():,.0f}")
            print(f"   Hidden equity: ${self.df.loc[has_estimate, 'prop13_hidden_equity'].median():,.0f}")
            print(f"   Benefit percentage: {self.df.loc[has_estimate, 'prop13_benefit_pct'].median():.1f}%")
            print(f"   Annual tax savings: ${self.df.loc[has_estimate, 'annual_tax_savings'].median():,.0f}")
            
            print(f"\n⏳ Ownership Tenure Analysis:")
            print(f"   (Shows how Prop 13 benefits increase with ownership duration)\n")
            
            tenure_bins = [0, 5, 10, 20, 100]
            tenure_labels = ['0-5 yrs', '5-10 yrs', '10-20 yrs', '20+ yrs']
            
            has_tenure = has_estimate & self.df['years_since_sale'].notna()
            if has_tenure.sum() > 0:
                self.df.loc[has_tenure, 'tenure_group'] = pd.cut(
                    self.df.loc[has_tenure, 'years_since_sale'],
                    bins=tenure_bins,
                    labels=tenure_labels
                )
                
                tenure_summary = self.df[has_tenure].groupby('tenure_group').agg({
                    'prop13_hidden_equity': ['count', 'median', 'mean'],
                    'prop13_benefit_pct': 'median',
                    'annual_tax_savings': ['median', 'sum']
                }).round(0)
                
                print(tenure_summary)
            
            print(f"\n🗺️  Estimation Method Distribution:")
            if 'estimation_method' in self.df.columns:
                method_dist = self.df[has_estimate]['estimation_method'].value_counts()
                for method, count in method_dist.items():
                    pct = (count / has_estimate.sum()) * 100
                    print(f"   {method}: {count:,} ({pct:.1f}%)")
            
            print(f"\n🏆 Top 10 Properties by Hidden Equity:")
            top_equity = self.df.nlargest(10, 'prop13_hidden_equity')[[
                'PARCEL_APN', 'SITE_ADDR', 'VAL_ASSD', 'estimated_total_market_value',
                'prop13_hidden_equity', 'years_since_sale'
            ]]
            print(top_equity.to_string(index=False))
        
        print("\n" + "="*80)
        print("✅ ANALYSIS COMPLETE")
        print("="*80)
        
        return self

        



# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """
    Main execution function
    """
    # Configuration
    FILEPATH = "sacramento_identified_parcels.csv"
    OUTPUT_FILENAME = "sacramento_property_valuations_enhanced.csv"
    CURRENT_YEAR = 2026
    
    # Analysis parameters
    LOOKBACK_YEARS = 3              # Use sales from last 3 years for comps
    INITIAL_H3_RESOLUTION = 11      # Start at sub-block level
    MIN_H3_RESOLUTION = 7           # Fall back to large area if needed
    MIN_COMPS_REQUIRED = 5          # Require at least 5 comps per hexagon
    
    print("\n" + "="*80)
    print("🚀 SACRAMENTO PROPERTY VALUATION ANALYSIS")
    print("   Accounting for Proposition 13 Tax Assessment Caps")
    print("="*80)
    print(f"\n⚙️  Configuration:")
    print(f"   Current Year: {CURRENT_YEAR}")
    print(f"   Comparable Sales Lookback: {LOOKBACK_YEARS} years")
    print(f"   Initial H3 Resolution: {INITIAL_H3_RESOLUTION} (sub-block)")
    print(f"   Minimum H3 Resolution: {MIN_H3_RESOLUTION} (large area)")
    print(f"   Minimum Comps Required: {MIN_COMPS_REQUIRED}")
    print("\n" + "="*80 + "\n")
    
    try:
        # Initialize valuator
        valuator = SacramentoPropertyValuator(FILEPATH, current_year=CURRENT_YEAR)
        
        # Execute analysis pipeline
        (valuator
         .load_data()
         .diagnose_sale_data()
         .deflate_assessed_values_to_base_year()
         .calculate_sale_assessment_ratios()
         .identify_recent_comparable_sales(
             lookback_years=LOOKBACK_YEARS,
             min_sale_price=50000,
             max_sale_price=10000000
         )
         .calculate_current_market_rates_by_h3(
             initial_resolution=INITIAL_H3_RESOLUTION,
             min_resolution=MIN_H3_RESOLUTION,
             min_comps_required=MIN_COMPS_REQUIRED
         )
         .estimate_current_market_values()
         .calculate_equity_metrics()
         .generate_output_file(OUTPUT_FILENAME)
         .generate_summary_report()
        )
        
        print(f"\n📁 Output saved to: {OUTPUT_FILENAME}")
        print("\n✨ Next steps:")
        print("   1. Review the output CSV for quality and accuracy")
        print("   2. Analyze properties with high hidden equity")
        print("   3. Cross-reference with vacancy indicators")
        print("   4. Identify potentially underutilized properties")
        print("   5. Consider land value capture opportunities")
        
    except FileNotFoundError:
        print(f"\n❌ Error: Could not find file '{FILEPATH}'")
        print("   Please ensure the CSV file is in the same directory as this script.")
    except Exception as e:
        print(f"\n❌ Error during analysis: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()