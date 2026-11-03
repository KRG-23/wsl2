"""Relocate Windows profile references in explicitly selected text configurations."""
import re


def windows_path(path):
    match = re.fullmatch(r'/mnt/([a-z])/(.*)', path)
    return match.group(1).upper() + ':\\' + match.group(2).replace('/', '\\') if match else ''


def relocate(text, old_home, new_home):
    if not old_home or old_home == new_home:
        return text
    old, new = windows_path(old_home), windows_path(new_home)
    replacements = [(old_home, new_home)]
    if old and new:
        replacements = [(old.replace('\\', '\\\\'), new.replace('\\', '\\\\')),
                        (old, new), (old.replace('\\', '/'), new.replace('\\', '/'))] + replacements
    for source, destination in replacements:
        # Do not rewrite a similarly named sibling account, e.g. old-user2.
        text = re.sub(re.escape(source) + r'''(?=$|[/\\\s"'])''', lambda _: destination, text)
    return text
