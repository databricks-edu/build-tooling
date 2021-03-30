import shutil
from collections import namedtuple
from pathlib import Path

ContentDir = namedtuple("ContentDir", ["kind", "path", "small"])
params = {
    "docx": {"dirs": (), "target": None},
    "ilt": {
        "dirs": (
            ContentDir("static", "css", True),
            ContentDir("assets", "img", False),
            ContentDir("static", "js", True),
            ContentDir("assets", "video", False),
        ),
        "target": "output/ilt",
    },
    "scorm": {
        "dirs": (
            ContentDir("static", "css", True),
            ContentDir("assets", "img", False),
            ContentDir("static", "js", True),
            ContentDir("assets", "video", False),
        ),
        "target": "output/scorm/html",
    },
}


def copytree(output_format: str, kind: str, copy_large: bool = False):
    dirs = [
        dir.path
        for dir in params[output_format]["dirs"]
        if dir.kind == kind and (dir.small or copy_large)
    ]
    target = params[output_format]["target"]
    if kind == "assets":
        kind = "work/assets"
    for dir in dirs:
        target_dir = f"{target}/{dir}"
        dir = f"/home/jovyan/{kind}/{dir}"
        shutil.rmtree(target_dir, ignore_errors=True)
        shutil.copytree(dir, target_dir)


def copy_scorm_files():
    scorm_files = [
        (
            "/home/jovyan/static/html/assessmenttemplate.html",
            "output/scorm/assessmenttemplate.html",
        ),
        (
            "/home/jovyan/static/scorm/xml/adlcp_rootv1p2.xsd",
            "output/scorm/adlcp_rootv1p2.xsd",
        ),
        ("/home/jovyan/static/scorm/xml/ims_xml.xsd", "output/scorm/ims_xml.xsd"),
        (
            "/home/jovyan/static/scorm/xml/imscp_rootv1p1p2.xsd",
            "output/scorm/imscp_rootv1p1p2.xsd",
        ),
        (
            "/home/jovyan/static/scorm/xml/imsmanifest.xml",
            "output/scorm/imsmanifest.xml",
        ),
        (
            "/home/jovyan/static/scorm/xml/imsmd_rootv1p2p1.xsd",
            "output/scorm/imsmd_rootv1p2p1.xsd",
        ),
    ]

    for file, target in scorm_files:
        Path(target).unlink(missing_ok=True)
        shutil.copyfile(file, target)
