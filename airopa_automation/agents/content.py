# AIropa Automation - Content Generator and Git Commit Agents

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from slugify import slugify

from airopa_automation.config import config

from .models import Article


class ContentGeneratorAgent:
    def __init__(self):
        self.output_dir = Path(config.content.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown(self, article: Article) -> Optional[Path]:
        """Generate markdown file for an article"""
        try:
            # Generate filename
            title_slug: str = slugify(article.title)
            date_str = (
                article.published_date.strftime("%Y-%m-%d")
                if article.published_date
                else datetime.now().strftime("%Y-%m-%d")
            )
            filename = f"{date_str}-{title_slug}.md"
            filepath: Path = self.output_dir / filename

            # Generate frontmatter
            frontmatter = self._generate_frontmatter(article)

            # Write markdown file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(frontmatter)
                f.write(f"\n\n{article.content}")

            return filepath

        except Exception as e:
            print(f"Error generating markdown for {article.title}: {e}")
            return None

    def _generate_frontmatter(self, article: Article) -> str:
        """Generate YAML frontmatter for markdown file"""
        frontmatter = "---\n"
        frontmatter += f'title: "{article.title}"\n'
        frontmatter += f'date: "{article.published_date.strftime("%Y-%m-%d") if article.published_date else datetime.now().strftime("%Y-%m-%d")}"\n'  # noqa: E501
        frontmatter += f'author: "{config.content.default_author}"\n'
        frontmatter += f'source: "{article.source}"\n'
        frontmatter += f'url: "{article.url}"\n'
        frontmatter += f'pillar: "{article.category}"\n'

        if article.country:
            frontmatter += f'country: "{article.country}"\n'

        if article.summary:
            frontmatter += f'description: "{article.summary[:160]}"\n'

        frontmatter += f'coverImage: "{config.content.default_cover_image}"\n'
        frontmatter += "isFeatured: false\n"
        frontmatter += "isAiGenerated: true\n"
        frontmatter += "---"

        return frontmatter


class GitCommitAgent:
    def __init__(self):
        import git

        self.repo_path = Path(config.git.repo_path)
        self.repo = git.Repo(self.repo_path)

    def commit_new_content(self, files: List[Path]) -> bool:
        """Commit new content files to git repository"""
        try:
            # Add files to git
            for file in files:
                relative_path = file.relative_to(self.repo_path)
                self.repo.index.add([str(relative_path)])

            # Commit changes
            import git

            self.repo.index.commit(
                config.git.commit_message,
                author=git.Actor(config.git.author_name, config.git.author_email),
            )

            return True

        except Exception as e:
            print(f"Error committing files to git: {e}")
            return False
