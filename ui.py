"""
ui.py - helpers that rebuild the shadcn/ui component class strings from the original
Lovable project (src/components/ui/*.tsx).

The original React code built class names with `cva()` and merged overrides with
`cn()` (tailwind-merge). `cn()` below is a small Python version of that merge, so
that, for example, `Button size="sm" className="h-8 px-2"` ends up with the same
final classes here as it did in React. Templates call these helpers, e.g.:

    <button class="{{ btn('hero', 'lg', 'text-base px-8') }}">
"""

import re

# --------------------------------------------------------------------------
# A tiny tailwind-merge: later classes win over earlier, conflicting ones
# --------------------------------------------------------------------------
_FONT_SIZE = re.compile(r"^text-(xs|sm|base|lg|xl|[2-9]xl|\[\d+(\.\d+)?(px|rem)\])$")
_GROUPS = [
    ("font-size", _FONT_SIZE),
    ("text-color", re.compile(r"^text-")),
    ("font-weight", re.compile(r"^font-(thin|extralight|light|normal|medium|semibold|bold|extrabold|black)$")),
    ("font-family", re.compile(r"^font-(mono|sans|serif|display|body)$")),
    ("height", re.compile(r"^h-")),
    ("width", re.compile(r"^w-")),
    ("min-height", re.compile(r"^min-h-")),
    ("px", re.compile(r"^px-")),
    ("py", re.compile(r"^py-")),
    ("pt", re.compile(r"^pt-")),
    ("pb", re.compile(r"^pb-")),
    ("p", re.compile(r"^p-")),
    ("gap", re.compile(r"^gap-")),
    ("justify", re.compile(r"^justify-")),
    ("bg-color", re.compile(r"^bg-(?!hero-gradient$|gold-gradient$)")),
    ("border-width", re.compile(r"^border(-[0248])?$")),
    ("border-color", re.compile(r"^border-(?!([0248]|[trblxy]|dashed|solid)$)")),
    ("transition", re.compile(r"^transition(-|$)")),
    ("duration", re.compile(r"^duration-")),
    ("rounded", re.compile(r"^rounded(-|$)")),
    ("shadow", re.compile(r"^shadow(-|$)")),
]
# group -> groups that it overrides when it comes later (p overrides px/py)
_ALSO_OVERRIDES = {"p": {"px", "py", "pt", "pb"}, "px": set(), "py": set()}


def _split(cls: str):
    """'hover:bg-accent' -> ('hover', 'bg-accent'); '[&_svg]:size-4' -> ('[&_svg]', 'size-4')."""
    depth, cut = 0, -1
    for i, ch in enumerate(cls):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        elif ch == ":" and depth == 0:
            cut = i
    return (cls[:cut], cls[cut + 1:]) if cut >= 0 else ("", cls)


def _group(util: str):
    for name, rx in _GROUPS:
        if rx.match(util):
            return name
    return None


def cn(*parts) -> str:
    result = []  # list of (variant, group, class)
    for part in parts:
        if not part:
            continue
        for cls in str(part).split():
            variant, util = _split(cls)
            grp = _group(util)
            if grp:
                kills = {grp} | _ALSO_OVERRIDES.get(grp, set())
                result = [r for r in result if not (r[0] == variant and r[1] in kills)]
            result.append((variant, grp, cls))
    # drop exact duplicates but keep order
    seen, out = set(), []
    for _, _, cls in result:
        if cls not in seen:
            seen.add(cls)
            out.append(cls)
    return " ".join(out)


# --------------------------------------------------------------------------
# Button (src/components/ui/button.tsx)
# --------------------------------------------------------------------------
_BUTTON_BASE = (
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium "
    "ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 "
    "focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none "
    "disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0"
)
_BUTTON_VARIANTS = {
    "default": "bg-primary text-primary-foreground hover:bg-primary/90",
    "destructive": "bg-destructive text-destructive-foreground hover:bg-destructive/90",
    "outline": "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
    "secondary": "bg-secondary text-secondary-foreground hover:bg-secondary/80",
    "ghost": "hover:bg-accent hover:text-accent-foreground",
    "link": "text-primary underline-offset-4 hover:underline",
    "hero": "bg-gold-gradient text-secondary-foreground font-semibold shadow-lg hover:shadow-xl "
            "hover:scale-[1.02] transition-all duration-200",
    "heroOutline": "border-2 border-accent text-accent hover:bg-accent hover:text-accent-foreground "
                   "transition-all duration-200",
}
_BUTTON_SIZES = {
    "default": "h-10 px-4 py-2",
    "sm": "h-9 rounded-md px-3",
    "lg": "h-11 rounded-md px-8",
    "icon": "h-10 w-10",
}


def btn(variant="default", size="default", cls="") -> str:
    return cn(_BUTTON_BASE, _BUTTON_VARIANTS[variant], _BUTTON_SIZES[size], cls)


# --------------------------------------------------------------------------
# Badge (badge.tsx)
# --------------------------------------------------------------------------
_BADGE_BASE = (
    "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold "
    "transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
)
_BADGE_VARIANTS = {
    "default": "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
    "secondary": "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
    "destructive": "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
    "outline": "text-foreground",
}


def badge(variant="default", cls="") -> str:
    return cn(_BADGE_BASE, _BADGE_VARIANTS[variant], cls)


# --------------------------------------------------------------------------
# Card (card.tsx)
# --------------------------------------------------------------------------
def card(cls="") -> str:
    return cn("rounded-lg border bg-card text-card-foreground shadow-sm", cls)


def card_header(cls="") -> str:
    return cn("flex flex-col space-y-1.5 p-6", cls)


def card_title(cls="") -> str:
    return cn("text-2xl font-semibold leading-none tracking-tight", cls)


def card_description(cls="") -> str:
    return cn("text-sm text-muted-foreground", cls)


def card_content(cls="") -> str:
    return cn("p-6 pt-0", cls)


# --------------------------------------------------------------------------
# Form controls (input.tsx, textarea.tsx, label.tsx, select.tsx)
# --------------------------------------------------------------------------
def input_cls(cls="") -> str:
    return cn(
        "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-base "
        "ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium "
        "file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none "
        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 "
        "disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
        cls,
    )


def textarea_cls(cls="") -> str:
    return cn(
        "flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm "
        "ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none "
        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 "
        "disabled:cursor-not-allowed disabled:opacity-50",
        cls,
    )


def label_cls(cls="") -> str:
    return cn(
        "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70", cls
    )


def select_trigger(cls="") -> str:
    return cn(
        "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background "
        "px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground "
        "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 "
        "disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1",
        cls,
    )


HELPERS = {
    "cn": cn,
    "btn": btn,
    "badge": badge,
    "card": card,
    "card_header": card_header,
    "card_title": card_title,
    "card_description": card_description,
    "card_content": card_content,
    "input_cls": input_cls,
    "textarea_cls": textarea_cls,
    "label_cls": label_cls,
    "select_trigger": select_trigger,
}
