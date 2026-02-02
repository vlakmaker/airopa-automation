#!/usr/bin/env python3
"""
Simple test runner for AIropa Automation project.
This script runs tests directly without using pytest to avoid dependency conflicts.
"""

import sys
import traceback
from tests.test_config import *
from tests.test_agents import *

def run_test(test_func, test_name):
    """Run a single test and report results"""
    try:
        test_func()
        print(f"✓ {test_name}")
        return True
    except Exception as e:
        print(f"✗ {test_name}")
        print(f"  Error: {e}")
        traceback.print_exc()
        return False

def run_all_tests():
    """Run all available tests"""
    print("Running AIropa Automation Tests...")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    # Config tests
    print("\n📋 Config Tests:")
    config_tests = [
        (test_scraper_config_defaults, "test_scraper_config_defaults"),
        (test_scraper_config_custom, "test_scraper_config_custom"),
        (test_database_config_defaults, "test_database_config_defaults"),
        (test_content_config_defaults, "test_content_config_defaults"),
        (test_git_config_defaults, "test_git_config_defaults"),
        (test_git_config_custom, "test_git_config_custom"),
        (test_full_config, "test_full_config"),
        (test_config_override, "test_config_override"),
    ]
    
    for test_func, test_name in config_tests:
        if run_test(test_func, test_name):
            passed += 1
        else:
            failed += 1
    
    # Agent tests
    print("\n🤖 Agent Tests:")
    
    # Article tests
    article_tests = TestArticle()
    article_test_methods = [
        (article_tests.test_article_creation, "test_article_creation"),
        (article_tests.test_article_generate_hash, "test_article_generate_hash"),
        (article_tests.test_article_with_optional_fields, "test_article_with_optional_fields"),
    ]
    
    for test_func, test_name in article_test_methods:
        if run_test(test_func, test_name):
            passed += 1
        else:
            failed += 1
    
    # Category classifier tests
    classifier_tests = TestCategoryClassifierAgent()
    classifier_test_methods = [
        (classifier_tests.test_classify_startup_category, "test_classify_startup_category"),
        (classifier_tests.test_classify_policy_category, "test_classify_policy_category"),
        (classifier_tests.test_classify_country, "test_classify_country"),
        (classifier_tests.test_classify_default_category, "test_classify_default_category"),
    ]
    
    for test_func, test_name in classifier_test_methods:
        if run_test(test_func, test_name):
            passed += 1
        else:
            failed += 1
    
    # Quality score tests
    scorer_tests = TestQualityScoreAgent()
    scorer_test_methods = [
        (scorer_tests.test_quality_score_short_content, "test_quality_score_short_content"),
        (scorer_tests.test_quality_score_good_content, "test_quality_score_good_content"),
        (scorer_tests.test_quality_score_max_is_one, "test_quality_score_max_is_one"),
    ]
    
    for test_func, test_name in scorer_test_methods:
        if run_test(test_func, test_name):
            passed += 1
        else:
            failed += 1
    
    # Scraper tests
    scraper_tests = TestScraperAgent()
    scraper_test_methods = [
        (scraper_tests.test_scraper_init, "test_scraper_init"),
    ]
    
    for test_func, test_name in scraper_test_methods:
        if run_test(test_func, test_name):
            passed += 1
        else:
            failed += 1
    
    # Content generator tests
    generator_tests = TestContentGeneratorAgent()
    generator_test_methods = [
        (generator_tests.test_content_generator_init, "test_content_generator_init"),
        (generator_tests.test_generate_frontmatter, "test_generate_frontmatter"),
    ]
    
    for test_func, test_name in generator_test_methods:
        if run_test(test_func, test_name):
            passed += 1
        else:
            failed += 1
    
    # Summary
    print("\n" + "=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
