import json

import toml


class Emoji:
    def __init__(self, unicode: str, code: str):
        self.unicode = unicode
        self.code = code


def parse_gitmoji_json() -> tuple[list[Emoji], list[Emoji], list[Emoji]]:
    major_tags: list[Emoji] = []
    minor_tags: list[Emoji] = []
    patch_tags: list[Emoji] = []

    with open("data/gitmoji.json", "r") as f:
        gitmojis = json.load(f)

    for gitmoji in gitmojis.get("gitmojis", []):
        emoji = Emoji(gitmoji.get("emoji", None), gitmoji.get("code", None))
        match gitmoji.get("semver", ""):
            case "major":
                major_tags.append(emoji)
            case "minor":
                minor_tags.append(emoji)
            case "patch":
                patch_tags.append(emoji)

    return major_tags, minor_tags, patch_tags


def apply_tags_to_pyproject_toml(
    major_tags: list[Emoji], minor_tags: list[Emoji], patch_tags: list[Emoji]
):
    data = toml.load("../pyproject.toml")
    commit_parser_options = (
        data.setdefault("tool", {})
        .setdefault("semantic_release", {})
        .setdefault("commit_parser_options", {})
    )
    commit_parser_options["major_tags"] = []
    for emoji in major_tags:
        commit_parser_options["major_tags"].append(emoji.code)
        commit_parser_options["major_tags"].append(emoji.unicode)
    commit_parser_options["minor_tags"] = []
    for emoji in minor_tags:
        commit_parser_options["minor_tags"].append(emoji.code)
        commit_parser_options["minor_tags"].append(emoji.unicode)
    commit_parser_options["patch_tags"] = []
    for emoji in patch_tags:
        commit_parser_options["patch_tags"].append(emoji.code)
        commit_parser_options["patch_tags"].append(emoji.unicode)

    with open("../pyproject.toml", "w") as f:
        f.write(toml.dumps(data))


if __name__ == "__main__":
    major_tags, minor_tags, patch_tags = parse_gitmoji_json()
    apply_tags_to_pyproject_toml(major_tags, minor_tags, patch_tags)
