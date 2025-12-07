import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.docs_core import analyze_documentation, ReadmeCategory

class TestDocsScoring(unittest.TestCase):
    def test_empty_readme(self):
        result = analyze_documentation("")
        self.assertEqual(result.total_score, 0)
        self.assertEqual(result.marketing_ratio, 0.0)

    def test_tutorial_readme(self):
        # High quality README with code blocks and structure
        content = """
# Project Title

## Overview
This is a great project that solves X.

## Installation
```bash
pip install my-project
```

## Usage
Here is a quickstart example:
```python
import my_project
my_project.run()
```

## Contributing
Please submit PRs.
"""
        result = analyze_documentation(content)
        # Should have high score due to essential categories + structure bonus
        self.assertGreater(result.total_score, 50)
        self.assertLessEqual(result.marketing_ratio, 0.1)
        
        # Check if structure bonus is applied (hard to check directly, but score should be decent)
        # Essential categories present: WHAT (Overview), HOW (Installation, Usage), CONTRIBUTING
        # Missing: WHY (maybe implicit in Overview), WHO, WHEN, REFERENCES
        
    def test_marketing_heavy_readme(self):
        content = """
# Best Project Ever

## Introduction
This is the world's best, revolutionary, game-changing solution.
It is an award-winning, state-of-the-art framework.
Unrivaled performance and superior quality.

## Features
- Cutting-edge technology
- Best-in-class support
"""
        result = analyze_documentation(content)
        # Marketing ratio should be high
        self.assertGreater(result.marketing_ratio, 0.3)
        
        # Score shouldn't be too high because it lacks HOW, CONTRIBUTING etc.
        # But it has WHAT (Introduction).
        self.assertLess(result.total_score, 50)

    def test_structure_bonus(self):
        content_no_bonus = """
# Title
## Usage
Just run the code.
"""
        result_no = analyze_documentation(content_no_bonus)
        
        content_bonus = """
# Title
## Usage
```python
print("Hello")
```
"""
        result_bonus = analyze_documentation(content_bonus)
        
        # Bonus one should be higher (assuming similar length/coverage impact)
        # Note: Coverage might differ slightly due to content length, but bonus is +5 or +10.
        # Let's verify the logic directly if possible, or rely on the score difference.
        self.assertGreater(result_bonus.total_score, result_no.total_score)

    def test_custom_required_sections(self):
        content = "# Title\n## Overview\nSome text."
        
        # Default requirements (WHAT, WHY, HOW, etc.)
        result_default = analyze_documentation(content)
        self.assertIn("HOW", result_default.missing_sections)
        
        # Custom requirements
        custom_reqs = ["WHAT", "Overview"] # Note: Overview is not a category, but let's assume user maps it or we use categories.
        # Wait, the implementation expects ReadmeCategory values as strings in required_sections.
        # Let's use valid category names.
        custom_reqs = ["WHAT", "HOW"]
        
        result_custom = analyze_documentation(content, custom_required_sections=custom_reqs)
        self.assertIn("HOW", result_custom.missing_sections)
        self.assertNotIn("WHY", result_custom.missing_sections) # WHY is not in custom reqs

if __name__ == "__main__":
    unittest.main()
