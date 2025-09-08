#!/usr/bin/env python3
"""
Test script for the LLM-based task classifier.
Run this script to test the classification functionality.
"""

from core.classifier import classify_task_type

def test_classification():
    """Test the classification function with various queries."""
    
    test_queries = [
        # NED queries
        "Who is John Smith?",
        "Find contact details for ABC Corporation",
        "Show me entity information about this person",
        "What do we know about contact 003Ws000004Fo3qIAC?",
        
        # PVI queries
        "Show me case details for case 500Ws000004Fo3qIAC",
        "What's the status of my support ticket?",
        "Case information please",
        "Support request details",
        
        # KQA queries
        "How do I reset my password?",
        "What are the business hours?",
        "General information about products",
        "How to configure email settings?",
        "What is the return policy?",
    ]
    
    print("Testing LLM-based Task Classification")
    print("=" * 50)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Query: '{query}'")
        try:
            classification = classify_task_type(query)
            print(f"   Classification: {classification}")
        except Exception as e:
            print(f"   Error: {str(e)}")
    
    print("\n" + "=" * 50)
    print("Classification test completed!")

if __name__ == "__main__":
    test_classification() 