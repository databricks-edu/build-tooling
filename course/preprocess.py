import glob
from typing import Dict, List

from course.convert import convert, convert_quiz

def generate_lesson_file_titles(course_info: Dict, format: str) -> List[List[str]]:
    file_titles = [[]]
    current_section = 0
    page_number = 0
    for file in glob.glob("md/*.md"):
        if "quiz" not in file:
            file_title = convert(file, format)
            file_titles[current_section].append((page_number, file_title))
        else:
            _, file_title = convert_quiz(file)
            file_titles[current_section].append((page_number, file_title))
            file_titles.append([])
            current_section += 1
        page_number += 1

    return file_titles


def generate_lesson_urls(course_info: Dict) -> List[str]:
    urls = []
    current_section = 0
    page_number = 0
    for file in glob.glob("md/*.md"):
        if "quiz" not in file:
            url = file.replace(".md", ".html").replace("md", course_info["base_url"])
            urls.append(url)
        else:
            url, _ = convert_quiz(file)
            urls.append(url)
            current_section += 1
        page_number += 1

    return urls
