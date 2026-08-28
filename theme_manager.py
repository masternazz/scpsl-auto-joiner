"""Local, deliberately small theme storage and CSS sanitization."""
import json
import os
import re


THEMES = {
    "violet": {"name": "Containment Violet", "accent": "#b186ff", "surface": "#17131d"},
    "amber": {"name": "Amber Control", "accent": "#e0a458", "surface": "#1b1713"},
    "slate": {"name": "Cold Slate", "accent": "#71b7d8", "surface": "#121920"},
    "light": {"name": "Daylight Control", "accent": "#6941c6", "surface": "#f4f1f8"},
    "light-warm": {"name": "Warm Paper", "accent": "#8a5a24", "surface": "#fbf7ef"},
    "light-slate": {"name": "Cool Slate Light", "accent": "#216b89", "surface": "#eef5f7"},
}
_FORBIDDEN = re.compile(r"(@import|url\s*\(|expression\s*\(|javascript\s*:|<\s*/?\s*script|on[a-z]+\s*=)", re.I)


def sanitize_css(css):
    if not isinstance(css, str) or len(css) > 100_000:
        raise ValueError("theme CSS is empty or too large")
    if _FORBIDDEN.search(css):
        raise ValueError("theme CSS contains import, external resource, script, or event-handler content")
    if "{" not in css or "}" not in css:
        raise ValueError("theme CSS must contain a rule")
    # Keep imported rules inside the app's namespace. This is intentionally a
    # conservative selector wrapper, not a general CSS parser.
    rules = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selectors, declarations = match.group(1).strip(), match.group(2).strip()
        if not selectors or not declarations:
            continue
        scoped = ", ".join(f".app-theme {selector.strip()}" for selector in selectors.split(","))
        rules.append(f"{scoped} {{ {declarations} }}")
    if not rules:
        raise ValueError("theme CSS contains no usable rules")
    return "\n".join(rules)


class ThemeManager:
    def __init__(self, data_dir):
        self.data_dir = os.path.abspath(os.fspath(data_dir))
        self.path = os.path.join(self.data_dir, "themes.json")

    def load(self):
        if not os.path.isfile(self.path):
            return {"preset": "violet", "custom": None}
        with open(self.path, encoding="utf-8") as stream:
            data = json.load(stream)
        return {"preset": data.get("preset", "violet"), "custom": data.get("custom")}

    def save(self, data):
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)

    def set_preset(self, preset):
        if preset not in THEMES:
            raise ValueError("unknown theme preset")
        data = self.load(); data["preset"] = preset; data["custom"] = None; self.save(data)
        return data

    def save_custom(self, filename, css):
        compiled = sanitize_css(css)
        data = self.load()
        data["custom"] = {"filename": os.path.basename(filename), "original": css, "compiled": compiled}
        self.save(data)
        return data["custom"]

    def reset(self):
        return self.set_preset("violet")
