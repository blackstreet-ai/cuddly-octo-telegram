#!/usr/bin/env python3
"""
Direct test of Notion API to verify token and database access
"""
import requests
import json

# Your Notion integration token from environment
import os
NOTION_TOKEN = os.getenv("NOTION_MCP_TOKEN", "your_token_here")

# Database ID from your config
DATABASE_ID = "2554cc35-4636-8145-aba9-c56e5b103977"

# Headers for Notion API
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def test_auth():
    """Test if the token is valid"""
    print("Testing Notion API authentication...")
    response = requests.get("https://api.notion.com/v1/users/me", headers=headers)
    if response.status_code == 200:
        user_info = response.json()
        print(f"✅ Authentication successful!")
        print(f"   Integration: {user_info['name']}")
        print(f"   Workspace: {user_info['bot']['workspace_name']}")
        return True
    else:
        print(f"❌ Authentication failed: {response.status_code}")
        print(f"   Error: {response.text}")
        return False

def test_database_access():
    """Test if we can access the database"""
    print(f"\nTesting database access (ID: {DATABASE_ID})...")
    response = requests.get(f"https://api.notion.com/v1/databases/{DATABASE_ID}", headers=headers)
    if response.status_code == 200:
        db_info = response.json()
        print(f"✅ Database access successful!")
        print(f"   Title: {db_info.get('title', [{}])[0].get('plain_text', 'Untitled')}")
        print(f"   Properties: {list(db_info.get('properties', {}).keys())}")
        return True
    else:
        print(f"❌ Database access failed: {response.status_code}")
        print(f"   Error: {response.text}")
        return False

def test_database_query():
    """Test querying the database for active topics"""
    print(f"\nTesting database query...")
    query_data = {
        "filter": {
            "property": "status",
            "select": {
                "equals": "Active"
            }
        },
        "sorts": [
            {
                "property": "updated_at",
                "direction": "descending"
            }
        ],
        "page_size": 5
    }
    
    response = requests.post(
        f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
        headers=headers,
        json=query_data
    )
    
    if response.status_code == 200:
        results = response.json()
        print(f"✅ Database query successful!")
        print(f"   Found {len(results['results'])} results")
        for i, result in enumerate(results['results'][:3]):
            title_prop = result.get('properties', {}).get('topic', {})
            if title_prop.get('type') == 'title':
                titles = title_prop.get('title') or []
                first = titles[0] if titles else {}
                title = first.get('plain_text', 'Untitled')
                print(f"   {i+1}. {title}")
        return True
    else:
        print(f"❌ Database query failed: {response.status_code}")
        print(f"   Error: {response.text}")
        return False

if __name__ == "__main__":
    print("=== Notion API Test ===")
    
    auth_ok = test_auth()
    if not auth_ok:
        exit(1)
    
    db_access_ok = test_database_access()
    if not db_access_ok:
        print("\n⚠️  Database access failed. Make sure:")
        print("   1. The integration is added to the database page")
        print("   2. The database ID is correct")
        exit(1)
    
    query_ok = test_database_query()
    if query_ok:
        print("\n🎉 All tests passed! Notion integration is working correctly.")
    else:
        print("\n⚠️  Database query failed, but basic access works.")
