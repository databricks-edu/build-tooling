import datetime
import json


def generate_output_path(course_name: str, format: str) -> str:
    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    file_handles = {
        "docx": f"output/docx/content-doc-{course_name}-{today}.md",
        "ilt": f"output/ilt/slides-{course_name}.md",
    }
    return file_handles[format]


def load_course_info():
    with open("course-info.json", "r") as course_info_file:
        course_info = json.loads(course_info_file.read())
        course_info["unique_string"] = course_info["title"].lower().replace(" ", "-")
        course_info[
            "base_url"
        ] = f"https://files.training.databricks.com/courses/{course_info['unique_string']}/v{course_info['version']}"
        return course_info
