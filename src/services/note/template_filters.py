"""Custom Jinja2 filters for note template formatting."""
import re
from typing import Any, List


def wikilink(value: Any) -> str:
    """
    Convert a string to Obsidian wikilink format.

    Args:
        value: String to convert to wikilink

    Returns:
        Wikilink formatted string: [[value]]

    Example:
        {{ "John Doe" | wikilink }} -> [[John Doe]]
    """
    if not value:
        return ""
    return f"[[{value}]]"


def wikilinks(items: List[Any]) -> str:
    """
    Convert a list of items to markdown bullet list with wikilinks.

    Args:
        items: List of items to convert

    Returns:
        Markdown bullet list with wikilinks

    Example:
        {{ people | wikilinks }} ->
        - [[Person 1]]
        - [[Person 2]]
    """
    if not items:
        return ""
    return "\n".join(f"- [[{item}]]" for item in items)


def mdlist(items: List[Any]) -> str:
    """
    Convert a list to markdown bullet points.

    Args:
        items: List of items to convert

    Returns:
        Markdown bullet list

    Example:
        {{ concepts | mdlist }} ->
        - Concept 1
        - Concept 2
    """
    if not items:
        return ""
    return "\n".join(f"- {item}" for item in items)


def safe_filename(title: str) -> str:
    """
    Create a filesystem-safe filename from a title.

    Args:
        title: Title to convert

    Returns:
        Safe filename string

    Example:
        {{ "My: Note?" | safe_filename }} -> My_Note
    """
    if not title:
        return "untitled"

    # Remove invalid characters
    safe = re.sub(r'[<>:"/\\|?*]', '', title)
    # Replace spaces with underscores
    safe = safe.replace(" ", "_")
    # Limit length
    safe = safe[:100]
    # Remove trailing periods and spaces
    safe = safe.rstrip(". ")
    return safe or "untitled"


def escape_pipe(value: Any) -> str:
    """
    Escape pipe characters for markdown tables.

    Args:
        value: Value to escape

    Returns:
        String with pipes escaped

    Example:
        {{ term | escape_pipe }} -> "value\\|with\\|pipes"
    """
    if not value:
        return ""
    return str(value).replace("|", "\\|")


# Dictionary of all custom filters
CUSTOM_FILTERS = {
    "wikilink": wikilink,
    "wikilinks": wikilinks,
    "mdlist": mdlist,
    "safe_filename": safe_filename,
    "escape_pipe": escape_pipe,
}
