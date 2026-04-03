import pandas as pd
import sys
import os

# Add current directory to path so we can import the agent module
sys.path.append(os.getcwd())

from agent.semantic_layer import build_semantic_layer

def run_demo():
    # 1. Create a sample dataset representing an Excel file
    data = {
        'Order_ID': ['ORD1', 'ORD2', 'ORD3', 'ORD4', 'ORD5'],
        'Date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-01', '2023-01-03', '2023-01-02']),
        'Category': ['Electronics', 'Furniture', 'Electronics', 'Furniture', 'Office'],
        'Sub_Category': ['Phones', 'Chairs', 'Laptops', 'Tables', 'Paper'],
        'Revenue_USD': [1200.50, 450.75, 2100.00, 890.25, 45.00],
        'Quantity_Sold': [2, 1, 3, 2, 10],
        'Tax_Rate': [0.15, 0.10, 0.15, 0.10, 0.05],
        'Is_Taxed': [True, True, True, True, False]
    }
    df = pd.DataFrame(data)

    # 2. Mock the column types (normally detected by schema_inference.py)
    column_types = {
        'Order_ID': 'identifier',
        'Date': 'datetime',
        'Category': 'categorical',
        'Sub_Category': 'categorical',
        'Revenue_USD': 'numeric',
        'Quantity_Sold': 'numeric',
        'Tax_Rate': 'numeric',
        'Is_Taxed': 'boolean'
    }

    # 3. Define columns for analysis
    analysis_columns = list(df.columns)

    # 4. Build the Semantic Layer
    # This is where the magic happens: classifying and generating KPIs
    print("Building Semantic Layer...\n")
    semantic_result = build_semantic_layer(df, column_types, analysis_columns)

    # 5. Output the Results
    print("==========================================")
    print("1. HUMAN-READABLE SUMMARY")
    print("==========================================")
    print(semantic_result['summary'])
    
    print("\n==========================================")
    print("2. AUTO-GENERATED KPIs")
    print("==========================================")
    for kpi in semantic_result['kpis']:
        print(f"- {kpi['name']}: {kpi['formula']}")
        print(f"  Description: {kpi['description']}")

    print("\n==========================================")
    print("3. DBT-STYLE YAML EXPORT")
    print("==========================================")
    print(semantic_result['yaml'])

    print("\n==========================================")
    print("4. COLUMN LINEAGE")
    print("==========================================")
    for raw, semantic in semantic_result['lineage'].items():
        print(f"{raw} -> {semantic}")

if __name__ == "__main__":
    run_demo()
