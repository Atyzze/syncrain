"""The logo in the middle of the rain: the NixOS snowflake that comes with syncrain, none, or any
picture.

A picture is made into the texture the shaders read as the shipped logos are made: a square, the
picture in its middle two thirds (the room round it is for the glow drawn from its blurred mip
levels), and under its transparent pixels the picture's own average colour, so that filtering at
its edge brings in no black. The web page does the same and puts the PNG it made into the settings
file (`data:image/png;base64,...`); such a texture is used as it is, so the desktop reads the very
pixels the page drew with.
"""
from __future__ import annotations

import base64
import io
import os

#: The shipped logos by the names the settings use, and by the files' own names.
SHIPPED = {"nixos": "white", "white": "white", "syncrain": "syncrain",
           # the NixOS logo in its own colours, gone in build 28 (under its rainbow it looked much as
           # the white one does): a settings file that still names it draws the NixOS logo instead
           "nixos-colours": "white", "colours": "white"}
SIDE = 1024
DATA_PREFIX = "data:image/png;base64,"


class LogoError(ValueError):
    pass


def normalize(choice: str) -> str:
    """'white', 'syncrain', 'none', a data URI or a picture file's path."""
    return SHIPPED.get(choice, choice)


def is_data(choice: str) -> bool:
    return isinstance(choice, str) and choice.startswith(DATA_PREFIX)


#: The largest side of a logo texture the page draws (and so the desktop takes).
MAX_SIDE = 4096


def decode(choice: str):
    """The PIL image a data URI holds; LogoError if it holds none."""
    from PIL import Image
    try:
        raw = base64.b64decode(choice[len(DATA_PREFIX):], validate=True)
        im = Image.open(io.BytesIO(raw))           # the header only: its size is known, nothing decoded
    except Exception as e:  # noqa: BLE001 - base64's and Pillow's errors are of every kind
        raise LogoError(f"the logo's picture cannot be read ({type(e).__name__})") from None
    if im.format != "PNG":
        raise LogoError("the logo's picture is not a PNG")
    if max(im.size) > MAX_SIDE:                    # before decoding: a small file can say a vast size
        raise LogoError(f"the logo's picture is larger than {MAX_SIDE} pixels")
    try:
        im.load()
    except Exception as e:  # noqa: BLE001
        raise LogoError(f"the logo's picture cannot be read ({type(e).__name__})") from None
    return im


def is_svg(path: str) -> bool:
    """An SVG by its name or its first bytes (an .svg named otherwise, or saved without a name)."""
    if path.lower().endswith((".svg", ".svgz")):
        return True
    try:
        with open(path, "rb") as fh:
            head = fh.read(2048).lstrip()
    except OSError:
        return False
    # a byte order mark, an XML declaration, a doctype or a comment can come first
    head = head.removeprefix(b"\xef\xbb\xbf").lstrip()
    return head.startswith(b"<") and b"<svg" in head


#: Where each family has librsvg's picture loader, which GTK reads an SVG with.
SVG_PACKAGES = "pacman -S librsvg, apt install librsvg2-common, dnf install librsvg2, zypper install gdk-pixbuf-loader-rsvg"


def open_svg(path: str):
    """An SVG drawn at SIDE * 2 on its longer side by GTK's picture loader (librsvg's), as a Pillow
    image: Pillow draws no SVG, and the page's browser does, so the desktop takes one too."""
    from PIL import Image
    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf, GLib
    except (ImportError, ValueError):
        raise LogoError(f"{path} is an SVG, which syncrain draws with GTK's picture loader (not found)") from None
    if "svg" not in {f.get_name() for f in GdkPixbuf.Pixbuf.get_formats()}:
        raise LogoError(f"{path} is an SVG, which needs librsvg's picture loader ({SVG_PACKAGES})")
    try:
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, SIDE * 2, SIDE * 2, True)
    except GLib.Error as e:
        raise LogoError(f"{path} is an SVG that cannot be drawn ({e.message})") from None
    mode = "RGBA" if pb.get_has_alpha() else "RGB"
    data = pb.read_pixel_bytes().get_data()
    return Image.frombuffer(mode, (pb.get_width(), pb.get_height()), data, "raw", mode, pb.get_rowstride(), 1).copy()


def open_picture(path: str):
    """A picture file as an image, upright as its camera meant it, decoded no larger than needed;
    LogoError for a file neither Pillow nor (for an SVG) GTK's loader reads."""
    from PIL import Image, ImageOps
    if is_svg(path):
        return open_svg(path)
    try:
        im = Image.open(path)
        im.draft("RGB", (SIDE * 2, SIDE * 2))      # a large JPEG decodes at a fraction of its size
        im = ImageOps.exif_transpose(im)
        im.load()
    except Exception as e:  # noqa: BLE001 - Pillow's errors for what it cannot read are of every kind
        raise LogoError(f"{path} is not a picture syncrain reads (PNG, JPEG, WebP, SVG; {type(e).__name__})") from None
    if max(im.size) > SIDE * 2:
        im.thumbnail((SIDE * 2, SIDE * 2))
    return im


def check(choice: str) -> str:
    """A logo the settings can name, or LogoError."""
    if choice in SHIPPED or choice == "none":
        return choice
    if is_data(choice):
        decode(choice)
        return choice
    if os.path.isfile(choice) and os.access(choice, os.R_OK):
        open_picture(choice)
        return choice
    raise LogoError(f"no logo {choice[:60]!r}: syncrain, nixos, none, or a picture file")


def prepare(im):
    """A picture as the logo texture: SIDE square, the picture in its middle two thirds."""
    from PIL import Image, ImageChops, ImageStat
    im = im.convert("RGBA")
    inner = round(SIDE * 2 / 3)
    k = inner / max(im.size)
    im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    r, g, b, a = im.split()
    weight = ImageStat.Stat(a).sum[0]
    if weight > 0:
        # multiply gives ch * a / 255: the alpha-weighted mean is its sum over the alphas' sum / 255
        avg = tuple(min(255, round(ImageStat.Stat(ImageChops.multiply(ch, a)).sum[0] * 255 / weight))
                    for ch in (r, g, b))
    else:
        avg = (255, 255, 255)
    seen = a.point(lambda v: 255 if v > 0 else 0)
    rgb = Image.composite(Image.merge("RGB", (r, g, b)), Image.new("RGB", im.size, avg), seen)
    out = Image.new("RGBA", (SIDE, SIDE), avg + (0,))
    out.paste(Image.merge("RGBA", (*rgb.split(), a)), ((SIDE - im.width) // 2, (SIDE - im.height) // 2))
    return out


def texture(choice: str, data_dir: str, bundled):
    """(width, height, RGBA bytes) of a logo other than none. `bundled` reads the shipped ones."""
    from .renderer import rgba_pil
    choice = normalize(choice)
    if choice in ("white", "syncrain"):
        return bundled(os.path.join(data_dir, f"logo-{choice}.png"))
    if is_data(choice):
        return rgba_pil(decode(choice))
    return rgba_pil(prepare(open_picture(choice)))
