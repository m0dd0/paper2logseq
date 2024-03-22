from pathlib import Path
import argparse
from typing import Dict
import logging

import pdf2bib
import pdf2doi

logger = logging.getLogger("paper2note")


def input_validate_path(path: str, must_exist: bool = False) -> Path:
    path = Path(path)
    if not path.is_absolute():
        path = Path.cwd() / path

    if must_exist and not path.exists():
        raise FileNotFoundError(f"{path} does not exist.")

    return path


def clean_metadata(extraction_result: Dict) -> Dict:
    """Clean the metadata extracted from a PDF file and add some aggrgated fields.

    Args:
        extraction_result (Dict): The metadata extracted from a PDF file as returned by pdf2bib.

    Returns:
        Dict: The cleaned metadata which is used for the templating operation.
    """
    metadata = extraction_result["metadata"]
    authors_list = metadata.get("author", [])
    authors_list = [f"{author['given']} {author['family']}" for author in authors_list]
    cleaned_metadata = {
        "title": metadata.get("title", "<no title found>"),
        "authors": ", ".join(authors_list) if authors_list else "<no authors found>",
        "year": metadata.get("year") or "????",
        "month": metadata.get("month") or "??",
        "day": metadata.get("day") or "??",
        "journal": metadata.get("journal")
        or metadata.get("ejournal")
        or "<no journal found>",
        "doi": metadata.get("doi") or "<no doi found>",
        "url": metadata.get("url") or "<no url found>",
        "volume": metadata.get("volume") or "<no volume found>",
        "page": metadata.get("page") or "<no page found>",
        "type": metadata.get("ENTRYTYPE") or "article",
        "abstract": extraction_result["validation_data"].get("summary")
        or "<no abstract found>",
        "bibtex": extraction_result.get("bibtex") or "<no bibtex found>",
    }
    for i, author in enumerate(authors_list):
        cleaned_metadata[f"author_{i+1}"] = author

    if authors_list:
        cleaned_metadata["author_last"] = authors_list[-1]

    return cleaned_metadata


def paper2note(
    pdf: Path,
    pdf_rename_pattern: str = None,
    note_target_folder: Path = None,
    note_template_path: Path = None,
    note_filename_pattern: str = None,
    pdf2bib_config: Dict = None,
    pdf2doi_config: Dict = None,
):
    """Create a reference note from the extracted metadata of a paper and save it in a folder.
    Optionally also renames the pdf file according to the metadata.

    Args:
        pdf (Path): Path to the pdf file of the paper.
        pdf_rename_pattern (str, optional): Pattern to rename the pdf file. All entries
            of the metadata can be used as placeholders. Placeholder must be in curly braces.
            If not provided no renaming will be executed.
        note_target_folder (Path, optional): Folder where the note should be saved to.
            Can be an absolute path or relative to the directory from wich the script is
            called. Defaults to the directory of the pdf file.
        note_template_path (Path, optional): Path to the note template. Can be an absolute
            path or relative to the directory from wich the script is called. Defaults to
            a default note template.
        note_filename_pattern (str, optional): Pattern to name the note file. All entries
            of the metadata can be used as placeholders. Placeholder must be in curly braces.
            Defaults to the same as the pdf_rename_pattern.
        pdf2bib_config (Dict, optional): Configurations for pdf2bib. Defaults to None.
        pdf2doi_config (Dict, optional): Configurations for pdf2doi. Defaults to None.
    """
    # handle default values, allow also str instead of Path, and make paths absolute
    pdf = input_validate_path(pdf, must_exist=True)
    if not pdf.suffix == ".pdf":
        raise ValueError("The provided file is not a pdf file.")

    pdf_rename_pattern = pdf_rename_pattern or pdf.stem

    note_target_folder = note_target_folder or pdf.parent
    note_target_folder = input_validate_path(note_target_folder)

    note_template_path = (
        note_template_path
        or Path(__file__).parent.parent / "templates" / "default_note_template.md"
    )
    note_template_path = input_validate_path(note_template_path, must_exist=True)

    note_filename_pattern = note_filename_pattern or pdf_rename_pattern

    pdf2bib_config = pdf2bib_config or {}
    pdf2doi_config = pdf2doi_config or {}

    # set config values for underlying libraries
    for config_name, config_value in pdf2doi_config.items():
        pdf2doi.config.set(config_name, config_value)
    for config_name, config_value in pdf2bib_config.items():
        pdf2bib.config.set(config_name, config_value)

    # extract metadata
    logger.info(f"Extracting metadata from {pdf}.")
    # TODO handle case of non-existing doi
    # TODO do not add doi to psd metadata
    result = pdf2bib.pdf2bib(str(pdf))
    data = clean_metadata(result)

    # rename pdf
    new_pdf_path = pdf.parent / f"{pdf_rename_pattern.format(**data)}.pdf"
    if new_pdf_path != pdf and not new_pdf_path.exists():
        logger.info(f"Renaming {pdf} to {new_pdf_path}.")
        pdf.rename(new_pdf_path)
    else:
        logger.info(f"Did not rename {pdf}.")

    # create note.md
    note_path = note_target_folder / f"{note_filename_pattern.format(**data)}.md"
    note_content = note_template_path.read_text().format(**data)

    if not note_path.exists():
        if not note_target_folder.exists():
            note_target_folder.mkdir(parents=True)

        logger.info(f"Creating note at {note_path}.")
        with open(note_path, "w") as f:
            f.write(note_content)
    else:
        logger.warning(f"Did not create note at {note_path} because it already exists.")


def parse_args() -> None:
    parser = argparse.ArgumentParser(
        description="Create a reference note from the extracted metadata of a paper and save it in a folder. Also renames the pdf file."
    )

    parser.add_argument("pdf", type=Path, help="Path to the pdf file of the paper.")
    parser.add_argument(
        "--pdf-rename-pattern",
        type=str,
        # default="{title}.pdf",
        help="Pattern to rename the pdf file. All entries of the metadata can be used as placeholders. Placeholder must be in curly braces. If not provided no renaming will be executed.",
    )
    parser.add_argument(
        "--note-target-folder",
        type=Path,
        help="Folder where the note should be saved to. Can be an absolute path or relative to the directory from wich the script is called. Defaults to the directory of the pdf file.",
    )
    parser.add_argument(
        "--note-template-path",
        type=Path,
        help="Path to the note template. Can be an absolute path or relative to the directory from wich the script is called. Defaults to a default note template.",
    )
    parser.add_argument(
        "--note-filename-pattern",
        type=str,
        # default="{title}.md",
        help="Pattern to name the note file. All entries of the metadata can be used as placeholders. Placeholder must be in curly braces. Defaults to the same name as the (renamed) pdf file.",
    )

    args = parser.parse_args()

    return args


def commandline_entrypoint() -> None:
    args = parse_args()
    paper2note(
        args.pdf,
        args.pdf_rename_pattern,
        args.note_target_folder,
        args.note_template_path,
        args.note_filename_pattern,
    )


if __name__ == "__main__":
    # for quick testing
    pdf_path = Path(
        "C:/Users/mohes/Documents/LogSeqNotes/assets/storages/Papers/2304.02532.pdf"
    )
    assert pdf_path.exists()

    paper2note(pdf_path)
