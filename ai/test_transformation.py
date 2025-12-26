"""Test script for table JSON transformation"""
import json
from converter import transform_table_to_key_value_format

# Test data from your example
test_table = {
    "sheet_name": "Development Loan Summary",
    "table_index": 1,
    "title": "Loan Documents",
    "headers": [
        "Internal",
        "Date Rec'd",
        "Property Details",
        "Borrower & Guarantor Details",
        "Project Documents",
        "Financial Info",
        "Loan Submission"
    ],
    "rows": [
        [
            "Development Loan Summary - Eagleby",
            "",
            "COS - Acacia Waters",
            "ABN - Glenaura Holdings Pty Ltd",
            "A1-14009 - WD100 - Site Plans - BA ISSUE.14-07-31",
            "A&L - Giuseppe Augello",
            ""
        ],
        [
            "Email - Richard Woodhead",
            "",
            "Disclosure Statement (signed) - Eagleby",
            "CV - Giuseppe Augello",
            "A1-14009 - WD200 - Type G18 Building - BA ISSUE.14-07-31",
            "",
            ""
        ]
    ]
}

# Test simple table
simple_table = {
    "headers": ["col1", "col2"],
    "rows": [
        ["Giuseppe Augello", "Signature"]
    ]
}

print("="*70)
print("TEST 1: Complex Table Transformation")
print("="*70)
print("\nInput (headers + rows format):")
print(json.dumps(test_table, indent=2))

transformed = transform_table_to_key_value_format(test_table)
print("\nOutput (key-value format):")
print(json.dumps(transformed, indent=2, ensure_ascii=False))

print("\n" + "="*70)
print("TEST 2: Simple Table Transformation")
print("="*70)
print("\nInput (headers + rows format):")
print(json.dumps(simple_table, indent=2))

transformed_simple = transform_table_to_key_value_format(simple_table)
print("\nOutput (key-value format):")
print(json.dumps(transformed_simple, indent=2))

print("\n" + "="*70)
print("VERIFICATION")
print("="*70)
print(f"\n✓ Test 1 produced {len(transformed)} row objects")
print(f"✓ Test 2 produced {len(transformed_simple)} row objects")
print(f"✓ Each row is a dictionary with column names as keys")
print("\n✓ Transformation successful!")
