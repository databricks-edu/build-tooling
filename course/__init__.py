import click
import glob
import json
import os
import pystache
from pathlib import Path
from course.convert import concatenate_markdown, convert, convert_quiz
from course.preprocess import generate_lesson_file_titles, generate_lesson_urls
from course.shutil import copy_scorm_files, copytree
from course.utility import generate_output_path, load_course_info
from course.write import write_page_titles, write_scorm_launch_html


@click.command()
@click.option("--format", help="output format: docx, ilt, scorm")
@click.option("--copy-large-assets/--no-copy-large-assets", default=False)
@click.option("--local/--no-local", default=False)
def main(format: str, copy_large_assets: bool, local: bool):

    course_info = load_course_info(local)

    copytree(format, "static", copy_large_assets)
    copytree(format, "assets", copy_large_assets)

    if format == "scorm":
        copy_scorm_files()
        urls = generate_lesson_urls(course_info)
        file_titles = generate_lesson_file_titles(course_info, format)
        write_page_titles(urls)
        write_scorm_launch_html(course_info, file_titles, urls)
    else:
        output_path = generate_output_path(course_info["unique_string"], format)
        concatenate_markdown(output_path)
        convert(output_path, format)
        os.remove(output_path)
        Path('current-header').unlink(missing_ok=True)
