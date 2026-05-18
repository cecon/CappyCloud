#!/usr/bin/env python3
"""
Example: Using skills-registry.json in code

This demonstrates how to read and use the central skills registry
in scripts, tools, or automation.
"""

import json
from pathlib import Path


def load_skills_registry():
    """Load the skills registry"""
    registry_path = Path("skills-registry.json")
    if not registry_path.exists():
        raise FileNotFoundError("skills-registry.json not found")

    with open(registry_path) as f:
        return json.load(f)


def example_1_list_all_skills():
    """Example 1: List all skills"""
    print("Example 1: List all skills")
    print("=" * 60)

    registry = load_skills_registry()

    for skill_name, skill_info in registry["skills"].items():
        print(f"  {skill_name:<30} ({skill_info['category']:<6})")

    print()


def example_2_skills_by_category():
    """Example 2: Group skills by category"""
    print("Example 2: Group skills by category")
    print("=" * 60)

    registry = load_skills_registry()

    # Group by category
    by_category = {}
    for skill_name, skill_info in registry["skills"].items():
        cat = skill_info["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(skill_name)

    for category, skills in sorted(by_category.items()):
        print(f"\n{category.upper()}:")
        for skill in sorted(skills):
            print(f"  • {skill}")

    print()


def example_3_get_skill_file():
    """Example 3: Get SKILL.md file path for a skill"""
    print("Example 3: Get SKILL.md path for a skill")
    print("=" * 60)

    registry = load_skills_registry()
    skill_name = "api-ux"

    if skill_name in registry["skills"]:
        skill = registry["skills"][skill_name]
        print(f"Skill: {skill_name}")
        print(f"File:  {skill['file']}")
        print(f"Path:  {skill['path']}")

    print()


def example_4_find_skills_by_keyword():
    """Example 4: Find skills by keyword in description"""
    print("Example 4: Find skills matching keyword 'design'")
    print("=" * 60)

    registry = load_skills_registry()
    keyword = "design".lower()

    for skill_name, skill_info in registry["skills"].items():
        description = skill_info["description"].lower()
        if keyword in description or keyword in skill_name:
            print(f"\n  {skill_name}")
            print(f"  → {skill_info['description'][:70]}...")

    print()


def example_5_generate_markdown_table():
    """Example 5: Generate markdown table of skills"""
    print("Example 5: Generate Markdown table")
    print("=" * 60)
    print()

    registry = load_skills_registry()

    print("| Skill | Category | Description |")
    print("|-------|----------|-------------|")

    for skill_name, skill_info in sorted(registry["skills"].items()):
        desc = skill_info["description"][:50] + "..." if len(skill_info["description"]) > 50 else skill_info["description"]
        print(f"| {skill_name} | {skill_info['category']} | {desc} |")

    print()


if __name__ == "__main__":
    # Run all examples
    example_1_list_all_skills()
    example_2_skills_by_category()
    example_3_get_skill_file()
    example_4_find_skills_by_keyword()
    example_5_generate_markdown_table()

    print("=" * 60)
    print("✅ All examples completed!")
