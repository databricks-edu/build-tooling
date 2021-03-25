import boto3
import glob
import os

VERSION = "v1.0.4"
COURSE = "introduction-to-development-workflows"
cache_large_files = False

s3 = boto3.client("s3")
for filename in glob.iglob("output/scorm/html/**/*", recursive=True):
    if ".git" not in filename and not os.path.isdir(filename):
        if cache_large_files and any(
            [
                filename.endswith("png"),
                filename.endswith("jpeg"),
                filename.endswith("mp4"),
            ]
        ):
            continue
        with open(filename, "rb") as file:
            content_types = {
                "html": "text/html",
                "js": "text/javascript",
                "css": "text/css",
                "mp4": "video/mp4",
                "jpeg": "image/jpeg",
                "png": "image/png",
            }
            if filename.endswith("png"):
                content_type = content_types["png"]
            elif filename.endswith("jpeg"):
                content_type = content_types["jpeg"]
            elif filename.endswith("mp4"):
                content_type = content_types["mp4"]
            elif filename.endswith("css"):
                content_type = content_types["css"]
            elif filename.endswith("js"):
                content_type = content_types["js"]
            elif filename.endswith("html"):
                content_type = content_types["html"]

            filename = filename.replace(
                "output/scorm/html", f"courses/{COURSE}/{VERSION}"
            )

            s3.upload_fileobj(
                file,
                "files.training.databricks.com",
                filename,
                ExtraArgs={
                    "ContentType": content_type,
                    "ContentDisposition": "inline",
                    "ACL": "public-read",
                },
            )
