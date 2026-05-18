#!/usr/bin/env python3
"""
Update skills-registry.json — Central registry of all available skills.

This script discovers all SKILL.md files in .agents/skills and .claude/skills,
extracts metadata, and generates a central registry that can be referenced
by CLAUDE.md and other tooling.

Usage:
    python3 scripts/update-skills-registry.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime


def extract_skill_info(skill_file: Path) -> dict:
    """
    Extract metadata from SKILL.md using manual YAML parser.

    Looks for frontmatter like:
    ---
    name: skill-name
    description: Skill description
    ---
    """
    with open(skill_file) as f:
        content = f.read()

    info = {}
    if content.startswith('---\n'):
        # Find closing frontmatter
        end_idx = content.find('\n---\n', 4)
        if end_idx != -1:
            frontmatter_text = content[4:end_idx]
            # Simple manual YAML parser
            for line in frontmatter_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    info[key] = value
    return info


def discover_skills() -> dict:
    """Discover all skills in .agents/skills, .claude/skills, and sandbox/skills"""
    skills = {}

    # Search in .agents/skills
    agents_skills_dir = Path(".agents/skills")
    if agents_skills_dir.exists():
        for skill_dir in agents_skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    info = extract_skill_info(skill_file)
                    skills[skill_dir.name] = {
                        "name": info.get("name", skill_dir.name),
                        "path": str(skill_dir),
                        "file": str(skill_file),
                        "category": "agents",
                        "description": info.get("description", "")
                    }

    # Search in .claude/skills
    claude_skills_dir = Path(".claude/skills")
    if claude_skills_dir.exists():
        for skill_dir in claude_skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    info = extract_skill_info(skill_file)
                    skills[skill_dir.name] = {
                        "name": info.get("name", skill_dir.name),
                        "path": str(skill_dir),
                        "file": str(skill_file),
                        "category": "claude",
                        "description": info.get("description", "")
                    }

    # Search in sandbox/skills (GLOBAL)
    sandbox_skills_dir = Path("sandbox/skills")
    if sandbox_skills_dir.exists():
        for skill_dir in sandbox_skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    info = extract_skill_info(skill_file)
                    skills[skill_dir.name] = {
                        "name": info.get("name", skill_dir.name),
                        "path": str(skill_dir),
                        "file": str(skill_file),
                        "category": "global",
                        "description": info.get("description", "")
                    }

    return dict(sorted(skills.items()))


def main():
    """Main entry point"""
    print("🔄 Updating skills registry...\n")

    skills = discover_skills()

    if not skills:
        print("❌ No skills found!")
        sys.exit(1)

    # Generate registry
    registry = {
        "version": "1.0",
        "lastUpdated": datetime.now().isoformat(),
        "totalSkills": len(skills),
        "description": "Central registry of all available skills for CappyCloud",
        "skills": skills
    }

    # Write registry
    registry_path = Path("skills-registry.json")
    with open(registry_path, "w") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    print(f"✅ Registry updated with {len(skills)} skills:\n")

    # Display by category
    agents_skills = [s for s in skills.values() if s["category"] == "agents"]
    claude_skills = [s for s in skills.values() if s["category"] == "claude"]
    global_skills = [s for s in skills.values() if s["category"] == "global"]

    if global_skills:
        print("🌍 Global Skills:")
        for skill in global_skills:
            desc = skill["description"][:50] + "..." if len(skill["description"]) > 50 else skill["description"]
            print(f"   • {skill['name']:<30} — {desc}")
        print()

    if agents_skills:
        print("📌 Agents Skills:")
        for skill in agents_skills:
            desc = skill["description"][:50] + "..." if len(skill["description"]) > 50 else skill["description"]
            print(f"   • {skill['name']:<30} — {desc}")
        print()

    if claude_skills:
        print("🎨 Claude Skills:")
        for skill in claude_skills:
            desc = skill["description"][:50] + "..." if len(skill["description"]) > 50 else skill["description"]
            print(f"   • {skill['name']:<30} — {desc}")
        print()

    print(f"📁 Saved to: {registry_path}")


if __name__ == "__main__":
    main()
