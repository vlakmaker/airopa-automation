# AIropa Automation Pipeline

import time
import logging
from typing import List
from pathlib import Path

from airopa_automation.agents import (
    ScraperAgent,
    CategoryClassifierAgent,
    QualityScoreAgent,
    ContentGeneratorAgent,
    GitCommitAgent,
    Article
)
from airopa_automation.config import config, ensure_directories

# Configure logging
logging.basicConfig(
    level=logging.INFO if config.debug else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AutomationPipeline:
    def __init__(self):
        ensure_directories()
        
        self.scraper = ScraperAgent()
        self.classifier = CategoryClassifierAgent()
        self.quality_assessor = QualityScoreAgent()
        self.content_generator = ContentGeneratorAgent()
        self.git_agent = GitCommitAgent()
    
    def run(self):
        """Run the complete automation pipeline"""
        logger.info("Starting AIropa automation pipeline")
        
        start_time = time.time()
        
        try:
            # Step 1: Scrape content
            logger.info("Step 1/5: Scraping content from sources")
            articles = self._scrape_content()
            logger.info(f"Scraped {len(articles)} articles")
            
            # Step 2: Classify content
            logger.info("Step 2/5: Classifying articles")
            classified_articles = self._classify_articles(articles)
            logger.info(f"Classified {len(classified_articles)} articles")
            
            # Step 3: Assess quality
            logger.info("Step 3/5: Assessing article quality")
            quality_articles = self._assess_quality(classified_articles)
            high_quality_articles = [a for a in quality_articles if a.quality_score >= 0.6]
            logger.info(f"Found {len(high_quality_articles)} high-quality articles")
            
            # Step 4: Generate content
            logger.info("Step 4/5: Generating markdown files")
            generated_files = self._generate_content(high_quality_articles)
            logger.info(f"Generated {len(generated_files)} markdown files")
            
            # Step 5: Commit to git
            logger.info("Step 5/5: Committing to git repository")
            if generated_files:
                success = self.git_agent.commit_new_content(generated_files)
                if success:
                    logger.info("Successfully committed new content")
                else:
                    logger.error("Failed to commit new content")
            
            # Log completion
            duration = time.time() - start_time
            logger.info(f"Pipeline completed in {duration:.2f} seconds")
            logger.info(f"Processed {len(articles)} articles, generated {len(generated_files)} files")
            
            return True
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            return False
    
    def _scrape_content(self) -> List[Article]:
        """Scrape content from all sources"""
        rss_articles = self.scraper.scrape_rss_feeds()
        web_articles = self.scraper.scrape_web_sources()
        
        # Combine and deduplicate
        all_articles = rss_articles + web_articles
        unique_articles = self._remove_duplicates(all_articles)
        
        return unique_articles
    
    def _classify_articles(self, articles: List[Article]) -> List[Article]:
        """Classify articles into categories"""
        classified = []
        
        for article in articles:
            try:
                classified_article = self.classifier.classify(article)
                classified.append(classified_article)
            except Exception as e:
                logger.error(f"Error classifying article {article.title}: {e}")
                continue
                
        return classified
    
    def _assess_quality(self, articles: List[Article]) -> List[Article]:
        """Assess article quality"""
        assessed = []
        
        for article in articles:
            try:
                assessed_article = self.quality_assessor.assess_quality(article)
                assessed.append(assessed_article)
            except Exception as e:
                logger.error(f"Error assessing quality for article {article.title}: {e}")
                continue
                
        return assessed
    
    def _generate_content(self, articles: List[Article]) -> List[Path]:
        """Generate markdown files for articles"""
        generated_files = []
        
        for article in articles:
            try:
                file_path = self.content_generator.generate_markdown(article)
                if file_path:
                    generated_files.append(file_path)
            except Exception as e:
                logger.error(f"Error generating content for article {article.title}: {e}")
                continue
                
        return generated_files
    
    def _remove_duplicates(self, articles: List[Article]) -> List[Article]:
        """Remove duplicate articles based on URL and hash"""
        seen_urls = set()
        seen_hashes = set()
        unique_articles = []
        
        for article in articles:
            # Check URL first
            if article.url in seen_urls:
                continue
                
            # Check content hash
            article_hash = article.generate_hash()
            if article_hash in seen_hashes:
                continue
                
            # Add to unique list
            seen_urls.add(article.url)
            seen_hashes.add(article_hash)
            unique_articles.append(article)
            
        return unique_articles

def main():
    """Main entry point for the automation pipeline"""
    pipeline = AutomationPipeline()
    success = pipeline.run()
    
    if not success:
        logger.error("Automation pipeline completed with errors")
        return 1
        
    logger.info("Automation pipeline completed successfully")
    return 0

if __name__ == "__main__":
    exit(main())