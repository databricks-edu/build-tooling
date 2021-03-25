import click
import glob
import json
import os
import pymustache
from build.convert import concatenate_markdown, convert, convert_quiz
from build.shutil import copy_scorm_files, copytree
from build.utility import generate_output_path, load_course_info


@click.command()
@click.option("--format", help="output format: docx, ilt, scorm")
@click.option("--copy-large-assets/--no-copy-large-assets", default=False)
def main(format: str, copy_large_assets: bool):

    course_info = load_course_info()

    copytree(format, "static", copy_large_assets)
    copytree(format, "assets", copy_large_assets)
    if format == "scorm":
        copy_scorm_files()

    if format == "scorm":
        urls = []
        file_titles = [[]]
        current_section = 0
        page_number = 0
        for file in glob.glob("md/*.md"):
            if "quiz" not in file:
                url = file.replace(".md", ".html").replace(
                    "md", course_info["base_url"]
                )
                file_title = convert(file, format)
                urls.append(url)
                file_titles[current_section].append((page_number, file_title))
            else:
                url, file_title = convert_quiz(file)
                urls.append(url)
                file_titles[current_section].append((page_number, file_title))
                file_titles.append([])
                current_section += 1
            page_number += 1
        with open("output/scorm/html/js/pageArray.js", "w") as page_array:
            page_array.write("var pageArray = " + json.dumps(urls))

        with open(
            "/home/jovyan/static/templates/launch-body.mustache", "r"
        ) as body_template_file, open(
            "/home/jovyan/static/templates/launch-head.mustache", "r"
        ) as head_template_file, open(
            "/home/jovyan/static/templates/launch-list-group-item-anchor.mustache", "r"
        ) as list_group_item_anchor_template_file, open(
            "/home/jovyan/static/templates/launch-list-group-item.mustache", "r"
        ) as list_group_item_template_file, open(
            "/home/jovyan/static/templates/launch-navbar-item.mustache", "r"
        ) as navbar_item_template_file, open(
            "/home/jovyan/static/templates/launch.mustache", "r"
        ) as launch_template_file, open(
            "output/scorm/launch.html", "w"
        ) as launch_html_file:

            head_template = head_template_file.read()
            head_html = pymustache.render(
                head_template, {"title": course_info["title"]}
            )

            navbar_item_template = navbar_item_template_file.read()
            list_group_item_anchor_template = (
                list_group_item_anchor_template_file.read()
            )
            list_group_item_template = list_group_item_template_file.read()
            list_group_items = ""
            navbar_items = ""

            for section_number, section_info in enumerate(file_titles):
                section_page_number, section_title = section_info[0]
                navbar_items += pymustache.render(
                    navbar_item_template,
                    {
                        "page_number": section_page_number,
                        "section_number": section_number + 1,
                    },
                )

                list_group_item_anchors = ""
                for i, lesson in enumerate(section_info[1:]):
                    lesson_page_number, lesson_title = lesson
                    list_group_item_anchors += pymustache.render(
                        list_group_item_anchor_template,
                        {
                            "page_number": lesson_page_number,
                            "section_number": section_number + 1,
                            "title": lesson_title,
                        },
                    )

                list_group_items += pymustache.render(
                    list_group_item_template,
                    {
                        "section_page_number": section_page_number,
                        "section_title": section_title,
                        "list_group_item_anchors": list_group_item_anchors,
                    },
                )

            body_template = body_template_file.read()
            body_html = pymustache.render(
                body_template,
                {
                    "title": course_info["title"],
                    "list_group_items": list_group_items,
                    "navbar_items": navbar_items,
                    "landing_src": urls[0],
                },
            )

            launch_template = launch_template_file.read()
            launch_html = pymustache.render(
                launch_template, {"body": body_html, "head": head_html}
            )

            launch_html_file.write(launch_html)
    else:
        output_path = generate_output_path(course_info["unique_string"], format)
        concatenate_markdown(output_path)
        convert(output_path, format)
        os.remove(output_path)
