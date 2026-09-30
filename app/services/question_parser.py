import re

from app.schemas.question_import import (
    ParsedQuestion,
    ParsedQuestionOption,
)


def parse_questions(text: str) -> list[ParsedQuestion]:
    text = text.strip()

    if not text:
        return []

    # Split questions using numbering:
    # 1. Question...
    # 2. Question...
    blocks = re.split(
        r"(?m)^\s*\d+\.\s+",
        text
    )

    blocks = [
        block.strip()
        for block in blocks
        if block.strip()
    ]

    questions = []

    for block in blocks:
        lines = [
            line.strip()
            for line in block.splitlines()
            if line.strip()
        ]

        question_lines = []
        options = []
        correct_answers = []

        topic = "General"
        difficulty = "MEDIUM"
        marks = 1
        negative_marks = 0

        current_section = "question"

        for line in lines:

            # Option:
            # A. Python
            # B) Java
            option_match = re.match(
                r"^([A-D])[\.\)]\s+(.+)$",
                line,
                re.IGNORECASE
            )

            if option_match:
                letter = option_match.group(1).upper()
                option_text = option_match.group(2).strip()

                option_order = ord(letter) - ord("A") + 1

                options.append(
                    ParsedQuestionOption(
                        option_text=option_text,
                        option_order=option_order
                    )
                )

                current_section = "options"
                continue

            # Answer:
            # Answer: B
            # Answer: B, C
            answer_match = re.match(
                r"^Answer\s*:\s*([A-D](?:\s*,\s*[A-D])*)$",
                line,
                re.IGNORECASE
            )

            if answer_match:
                answers = answer_match.group(1)

                correct_answers = [
                    ord(letter.upper()) - ord("A") + 1
                    for letter in re.findall(
                        r"[A-D]",
                        answers,
                        re.IGNORECASE
                    )
                ]

                current_section = "metadata"
                continue

            # Topic:
            topic_match = re.match(
                r"^Topic\s*:\s*(.+)$",
                line,
                re.IGNORECASE
            )

            if topic_match:
                topic = topic_match.group(1).strip()
                current_section = "metadata"
                continue

            # Difficulty:
            difficulty_match = re.match(
                r"^Difficulty\s*:\s*(EASY|MEDIUM|HARD)$",
                line,
                re.IGNORECASE
            )

            if difficulty_match:
                difficulty = (
                    difficulty_match.group(1)
                    .upper()
                )
                current_section = "metadata"
                continue

            # Marks:
            marks_match = re.match(
                r"^Marks\s*:\s*(\d+)$",
                line,
                re.IGNORECASE
            )

            if marks_match:
                marks = int(marks_match.group(1))
                current_section = "metadata"
                continue

            # Negative marks:
            negative_marks_match = re.match(
                r"^Negative\s*Marks\s*:\s*(\d+)$",
                line,
                re.IGNORECASE
            )

            if negative_marks_match:
                negative_marks = int(
                    negative_marks_match.group(1)
                )
                current_section = "metadata"
                continue

            # Everything before options belongs to
            # the question text.
            if current_section == "question":
                question_lines.append(line)

        question_text = " ".join(question_lines).strip()

        if not question_text:
            continue

        questions.append(
            ParsedQuestion(
                question_text=question_text,
                options=options,
                correct_answers=correct_answers,
                topic=topic,
                difficulty=difficulty,
                marks=marks,
                negative_marks=negative_marks,
            )
        )

    return questions