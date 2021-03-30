import json
import pystache
from typing import Dict, List
from course.utility import read_template


def write_page_titles(urls: List[str]):
    with open("output/scorm/html/js/pageArray.js", "w") as page_array:
        page_array.write("var pageArray = " + json.dumps(urls))


def write_scorm_launch_html(
    course_info: Dict, file_titles: List[List[str]], urls: List[str]
):

    launch_template = read_template("main")
    head_template = read_template("head")
    body_template = read_template("body")
    navbar_item_template = read_template("navbar-item")
    list_group_item_template = read_template("list-group-item")
    list_group_item_anchor_template = read_template("list-group-item-anchor")

    head_html = pystache.render(head_template, {"title": course_info["title"]})

    list_group_items = ""
    navbar_items = ""

    for section_number, section_info in enumerate(file_titles):
        section_page_number, section_title = section_info[0]
        navbar_items += pystache.render(
            navbar_item_template,
            {
                "page_number": section_page_number,
                "section_number": section_number + 1,
            },
        )

        list_group_item_anchors = ""
        for i, lesson in enumerate(section_info[1:]):
            lesson_page_number, lesson_title = lesson
            list_group_item_anchors += pystache.render(
                list_group_item_anchor_template,
                {
                    "page_number": lesson_page_number,
                    "section_number": section_number + 1,
                    "title": lesson_title,
                },
            )

        list_group_items += pystache.render(
            list_group_item_template,
            {
                "section_page_number": section_page_number,
                "section_title": section_title,
                "list_group_item_anchors": list_group_item_anchors,
            },
        )

    body_html = pystache.render(
        body_template,
        {
            "title": course_info["title"],
            "list_group_items": list_group_items,
            "navbar_items": navbar_items,
            "landing_src": urls[0],
        },
    )

    launch_html = pystache.render(
        launch_template, {"body": body_html, "head": head_html}
    )

    with open("output/scorm/launch.html", "w") as launch_html_file:
        launch_html_file.write(launch_html)
