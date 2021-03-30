import glob
import os
import shutil

from bs4 import BeautifulSoup
import pystache
import pypandoc


def add_background_class(html_text: str):
    def update_class(el, _class):
        el.attrs["class"] = el.attrs.get("class", "") + " " + _class
        del el.attrs["id"]
        return el

    soup = BeautifulSoup(html_text, "html.parser")
    h1s = soup.findAll("h1")

    this_title = h1s[0].text
    for h1 in h1s:
        if "Section" in h1.text:
            h1 = update_class(h1, "slide-section-header")
        if "Lesson" in h1.text:
            h1 = update_class(h1, "slide-lesson-header")
    return (pypandoc.convert_text(soup, format="html", to="md"), this_title)


def concatenate_markdown(output_path: str):
    with open(output_path, "w") as outfile:
        for file in glob.glob("md/*.md"):
            if "quiz" not in file:
                with open(file, "r") as infile:
                    shutil.copyfileobj(infile, outfile)
                    outfile.write("\n")


def convert(filename: str, format: str):

    extra_args = {
        "docx": ["--resource-path=assets", "--resource-path=static"],
        "ilt": [
            "-t", "revealjs",
            "--standalone",
            "--slide-level",
            "2",
            "-V",
            "theme=white",
            "--no-highlight",
        ],
        "scorm" : [
            "--shift-heading-level-by", "2",
            "--standalone"
        ]
    }

    markdown_text = load_markdown_as_html(filename)
    markdown_text, this_title = add_background_class(markdown_text)

    if format == "docx":
        kwargs = {
            "source": markdown_text,
            "format": "md",
            "to": format,
            "outputfile": "output/docx/"
            + os.path.basename(filename.replace(".md", ".docx")),
            "extra_args": extra_args[format],
        }
    elif format == "ilt":
        kwargs = {
            "source": markdown_text,
            "format": "md",
            "to": "html",
            "outputfile": "output/ilt/"
            + os.path.basename(filename.replace(".md", ".html")),
            "filters" : ["/home/jovyan/static/pandoc-filters/hr-to-header.py"],
            "extra_args": extra_args[format],
        }
    elif format == "scorm":
        kwargs = {
            "source": markdown_text,
            "format": "md",
            "to": "html",
            "outputfile": "output/scorm/html/"
            + os.path.basename(filename.replace(".md", ".html")),
            "extra_args": extra_args[format],
        }
    pypandoc.convert_text(**kwargs)
    return this_title


def convert_quiz(filename: str):
    section = (
        filename.replace("md", "").replace("-quiz.", "").replace("/", "").lstrip("0")
    )
    quiz_html = load_markdown_as_html(filename)

    soup = BeautifulSoup(quiz_html, "html.parser")
    questions = [h1.text for h1 in soup.findAll("h1")]
    answer_lists = [
        [child.text.replace("CORRECT", "") for child in ol.findAll("li")]
        for ol in soup.findAll("ol")
    ]
    correct_answers = [
        [
            child.text.replace("CORRECT", "")
            for child in ol.findAll("li")
            if "CORRECT" in child.text
        ].pop()
        for ol in soup.findAll("ol")
    ]
    quizQuestions = [
        {
            "number": i + 1,
            "section": section,
            "question": question,
            "answer_1": answer_list[0].lstrip(),
            "answer_2": answer_list[1].lstrip(),
            "answer_3": answer_list[2].lstrip(),
            "answer_4": answer_list[3].lstrip(),
            "correct": correct_answer.lstrip(),
        }
        for i, (question, answer_list, correct_answer) in enumerate(
            zip(questions, answer_lists, correct_answers)
        )
    ]
    template = """
    test.AddQuestion( new Question ("com.databricks.academy.introdevworkflows.interactions.sec_{{section}}_{{number}}",
                                    "{{question}}",
                                    QUESTION_TYPE_CHOICE,
                                    new Array(
                                      "{{answer_1}}",
                                      "{{answer_2}}",
                                      "{{answer_3}}",
                                      "{{answer_4}}"
                                    ),
                                      "{{correct}}",
                                    "obj_section_{{section}}")
                    );
    """

    output = "\n".join(
        [pystache.render(template, quizQuestion) for quizQuestion in quizQuestions]
    )

    with open(f"output/scorm/html/quiz/questions-{section}.js", "w") as question_file:
        question_file.write(output)

    return (f"assessmenttemplate.html?questions={section}", f"Section {section} Quiz")


def load_markdown_as_html(filename: str):
    return pypandoc.convert_file(filename, to="html")
