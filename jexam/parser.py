#####################################
##### Notebook Parser for jExam #####
#####################################

import re
import os
import yaml
import copy
import json
import pprint
import hashlib
import pathlib
import nbformat
import numpy as np

from textwrap import dedent
from collections import namedtuple

from .utils import str_to_doctest, generate


#---------------------------------------------------------------------------------------------------
# GLOBAL VARIABLES
#---------------------------------------------------------------------------------------------------

NB_VERSION = 4
COMMENT_PREFIX = "#"
TEST_HEADERS = ["TEST", "HIDDEN TEST"]
ALLOWED_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]*')
TEST_REGEX = r"(##\s*(hidden\s*)?test\s*##|#\s*(hidden\s*)?test)"
MD_SOLUTION_REGEX = r"(<strong>|\*{2})solution:?(<\/strong>|\*{2})"
MARKDOWN_ANSWER_CELL_TEMPLATE = nbformat.v4.new_markdown_cell(
    "_Type your answer here, replacing this text._"
)

BEGIN_REGEXES = {
    "exam": r"\s*BEGIN EXAM\s*",
    "introduction": r"\s*BEGIN INTRODUCTION\s*",
    "question": r"\s*BEGIN QUESTION\s*",
    "version": r"\s*BEGIN VERSION\s*",
    "conclusion": r"\s*BEGIN CONCLUSION\s*",
}

END_REGEXES = {
    "introduction": r"\s*END INTRODUCTION\s*",
    "question": r"\s*END QUESTION\s*",
    "version": r"\s*END VERSION\s*",
    "conclusion": r"\s*END CONCLUSION\s*",
}


#---------------------------------------------------------------------------------------------------
# HELPFUL CLASSES
#---------------------------------------------------------------------------------------------------

class Version:
    """
    Represents a single version of a question. Contains methods to parse its cells for solution removal
    and generating tests.

    Args:
        cells (``list`` of ``nbformat.NotebookNode``): the list of original (unparsed) cells that define
            this version

    Attributes:
        original_cells (``list`` of ``nbformat.NotebookNode``): the original cells from the notebook 
            (incl. test cells and solutions)
        cells_with_solutions (``list`` of ``nbformat.NotebookNode``): the original cells with test 
            cells removed and solutions left
        cells_without_solutions (``list`` of ``nbformat.NotebookNode``): the original cells with 
            solutions and test cells removed
        tests (``list`` of ``Test``): the tests for this version as named tuples
    """
    def __init__(self, cells):
        self.original_cells = cells
        self.cells_with_solutions = None
        self.cells_without_solutions = None
        self.tests = []

    def _parse_cells(self):
        """
        Parses the original cells of this version to remove test cells and solutions. Populates 
        ``cells_with_solutions`` and ``cells_without_solutions``.
        """
        self.cells_with_solutions = []
        self.cells_without_solutions = []
        for cell in self.original_cells:
            if is_test_cell(cell):
                self.tests.append(read_test(cell))
            else:
                self.cells_with_solutions.append(cell)
                self.cells_without_solutions.append(replace_cell_solutions(cell))

    def get_cells(self, include_solutions):
        """
        Returns the list of parsed cells for this version. If parsing hasn't been done yet, it parses
        this version.

        Args:
            include_solutions (``bool``): whether to return the cells that contain solutions
    
        Returns:
            ``list`` of ``nbformat.NotebookNode``: the list of parsed cells
        """
        if self.cells_with_solutions is None or self.cells_without_solutions is None:
            self._parse_cells()
        if include_solutions:
            return self.cells_with_solutions
        return self.cells_without_solutions

    def any_public_tests(self):
        """
        Returns whether this version has any public tests.

        Returns:
            ``bool``: whether this version has any public tests
        """
        return any([not t.hidden for t in self.tests])
    
    def get_hash(self):
        """
        Returns a SHA-256 hash of this version.

        Returns:
            ``str``: the hash of this version
        """
        source = ""
        for cell in self.original_cells:
            source += "\n".join(get_source(cell))
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

class Question:
    """
    Represents a single question in the exam with multiple versions.

    Args:
        versions (``list`` of ``Version``): the versions of this question
        points (``int``): the number of points this question is worth
        manual (``bool``): whether this question is manually graded

    Attributes:
        versions (``list`` of ``Version``): the versions of this question
        points (``int``): the number of points this question is worth
        manual (``bool``): whether this question is manually graded
        unused_versions (``list`` of ``int``): a list of indices in ``versions`` that haven't been 
            used yet; repopulated when this list becomes empty
    """
    def __init__(self, versions, points, manual):
        if not isinstance(versions, list):
            self.versions = [versions]
        else:
            self.versions = versions
        
        self.points = points
        self.manual = manual
        self.unused_versions = list(range(len(self.versions)))

    def choose_version(self):
        """
        Randomly selects a version of this question from ``unused_versions`` and returns it. Removes 
        its index from ``unused_versions`` Repopulates``unused_versions`` if empty.

        Returns:
            ``Version``: the chosen version
        """
        if  len(self.unused_versions) == 0:
            self.unused_versions = list(range(len(self.versions)))
        idx = np.random.choice(self.unused_versions)
        self.unused_versions.remove(idx)
        version = self.versions[idx]
        return version

class Exam:
    """
    Contains configurations and lists of cells/objects that define an Exam. This class is not designed
    to be instantiated but to have its class attributes edited directly.

    Attributes:
        config (``dict``): configurations for the exam
        questions (``list` of ``Question``): the questions that make up this exam
        introduction (``list`` of ``nbformat.NotebookNode``): a list of preamble cells for the notebook
        conclusion (``list`` of ``nbformat.NotebookNode``): a list of postamble cells for the notebook
        autograder_format (``str``): a string defining the autograder output format; either "otter"
            for Otter-Grader or "ok" for OkPy
    """
    config = {}
    questions = []
    introduction = []
    conclusion = []
    autograder_format = "otter"

    @classmethod
    def otter(cls):
        """
        Returns whether the autograder format for this exam is Otter-Grader
        
        Returns:
            ``bool``: whether the autograder format for this exam is Otter-Grader 
        """
        return cls.autograder_format == "otter"
    
    @classmethod
    def ok(cls):
        """
        Returns whether the autograder format for this exam is OkPy
        
        Returns:
            ``bool``: whether the autograder format for this exam is OkPy 
        """
        return cls.autograder_format == "ok"

def create_and_write_exam_instance(output_dir, nb_name, num_questions):
    """
    Creates a single exam notebook using nbformat with solutions removes and writes that notebook at
    ``{{ output_dir }}/{{ nb_name }}``. Randomly selects ``num_questions`` questions from ``Exam.questions``
    and includes test cells if ``Exam.config.get("public_tests", False)`` is ``True``. 

    Args:
        output_dir (``pathlib.Path``): the path to the output directory
        nb_name (``str``): the filename of the notebook
        num_questions (``int``): the number of questions for the exam
    """
    test_dir = output_dir / 'tests'

    if Exam.config.get("public_tests", False):
        os.makedirs(test_dir, exist_ok=True)
    else:
        os.makedirs(output_dir, exist_ok=True)

    student = nbformat.v4.new_notebook()

    # create autograder config file for this dir
    if Exam.otter():
        gen_otter_file(output_dir / nb_name)
        ok_path = None
    elif Exam.ok():
        ok_path = gen_dot_ok(output_dir / nb_name, Exam.config["endpoint"])
    
    # init cell
    if Exam.config.get("init_cell", True):
        student.cells.append(gen_init_cell(ok_path))
    
    # introduction
    student.cells.extend(Exam.introduction)

    # get question indices
    question_idx = list(range(len(Exam.questions)))
    np.random.shuffle(question_idx)
    question_idx = question_idx[:num_questions]

    # questions
    for i in range(num_questions):
        student.cells.append(gen_question_header_cell(i + 1))

        question = Exam.questions[question_idx[i]]
        version = question.choose_version()
        student.cells.extend(version.get_cells(False))

        if not question.manual and Exam.config.get("public_tests", False):
            student.cells.append(gen_test_cell(
                version.get_hash(),
                question.points,
                version.tests,
                test_dir
            ))
    
    # remove hidden tests
    if Exam.config.get("public_tests", False):
        remove_hidden_tests(test_dir)
    
    # conclusion
    student.cells.extend(Exam.conclusion)

    # check all cell
    if Exam.config.get("check_all_cell", True) and Exam.config.get("public_tests", False):
        student.cells.extend(gen_check_all_cell())

    # export cell
    if Exam.config.get("export_cell", True):
        export_cell = Exam.config.get("export_cell", True)
        if export_cell is True:
            export_cell = {}

        student.cells.extend(gen_export_cells(
            export_cell.get('instructions', ''), 
            pdf = export_cell.get('pdf', True),
            filtering = export_cell.get('filtering', True)
        ))

    # remove output
    remove_output(student)
    
    # write notebooks
    nbformat.write(student, output_dir / nb_name)

def create_and_write_autograder_exam(output_dir, nb_name):
    """
    Formats and writes a solutions notebook containing all questions and all versions to the path
    ``{{ output_dir }}/{{ nb_name }}``. Also creates test cells and autograder tests files included
    in the ``tests`` subdirectory of ``output_dir``.

    Args:
        output_dir (``pathlib.Path``): the path to the output directory
        nb_name (``str``): the filename of the notebook
    """
    test_dir = output_dir / 'tests'
    os.makedirs(test_dir, exist_ok=True)

    autograder = nbformat.v4.new_notebook()

    # create autograder config file for this dir
    if Exam.otter():
        gen_otter_file(output_dir / nb_name)
        ok_path = None
    elif Exam.ok():
        ok_path = gen_dot_ok(output_dir / nb_name, Exam.config["endpoint"])

    # init cell
    if Exam.config.get("init_cell", True):
        autograder.cells.append(gen_init_cell(ok_path))
    
    # introduction
    autograder.cells.extend(Exam.introduction)

    # # get question indices
    # question_idx = list(range(len(Exam.questions)))
    # np.random.shuffle(question_idx)
    # question_idx = question_idx[:num_questions]

    # questions
    for i, question in enumerate(Exam.questions):
        autograder.cells.append(gen_question_header_cell(i + 1))

        # question = Exam.questions[question_idx[i]]

        for j, version in enumerate(question.versions):
            autograder.cells.append(gen_version_header_cell(j + 1))
            autograder.cells.extend(version.get_cells(True))

            if not question.manual:
                autograder.cells.append(gen_test_cell(
                    version.get_hash(),
                    question.points,
                    version.tests,
                    test_dir
                ))
    
    # conclusion
    autograder.cells.extend(Exam.conclusion)

    # check all cell
    if Exam.config.get("check_all_cell", True):
        autograder.cells.extend(gen_check_all_cell())

    # export cell
    if Exam.config.get("export_cell", True):
        export_cell = Exam.config.get("export_cell", True)
        if export_cell is True:
            export_cell = {}

        autograder.cells.extend(gen_export_cells(
            export_cell.get('instructions', ''), 
            pdf = export_cell.get('pdf', True),
            filtering = export_cell.get('filtering', True)
        ))

    # # remove output
    # remove_output(autograder)
    
    # write notebooks
    nbformat.write(autograder, output_dir / nb_name)


#---------------------------------------------------------------------------------------------------
# UTILITIES
#---------------------------------------------------------------------------------------------------

def get_source(cell):
    """Gets the source code of a cell in a way that works for both nbformat and JSON
    
    Args:
        cell (``nbformat.NotebookNode``): notebook cell
    
    Returns:
        ``list`` of ``str``: each line of the cell source
    """
    source = cell['source']
    if isinstance(source, str):
        return cell['source'].split("\n")
    elif isinstance(source, list):
        return [l.strip() for l in source]
    assert False, f'unknown source type: {type(source)}'

def remove_output(nb):
    """Removes all outputs from a notebook
    
    Args:
        nb (``nbformat.NotebookNode``): a notebook
    """
    for cell in nb['cells']:
        if 'outputs' in cell:
            cell['outputs'] = []

def lock(cell):
    """Makes a cell non-editable and non-deletable

    Args:
        cell (``nbformat.NotebookNode``): cell to be locked
    """
    m = cell['metadata']
    m["editable"] = False
    m["deletable"] = False

def is_raw_cell(cell):
    """Returns whether a cell is a raw cell

    Args:
        cell (``nbformat.NotebookNode``): the cell in question

    Returns:
        ``bool``: whether a cell is a raw cell
    """
    return cell["cell_type"] == "raw"

def is_markdown_cell(cell):
    """Returns whether a cell is a Markdown cell

    Args:
        cell (``nbformat.NotebookNode``): the cell in question

    Returns:
        ``bool``: whether a cell is a Markdown cell
    """
    return cell["cell_type"] == "markdown"

def is_code_cell(cell):
    """Returns whether a cell is a code cell

    Args:
        cell (``nbformat.NotebookNode``): the cell in question
    
    Returns:
        ``bool``: whether a cell is a code cell
    """
    return cell["cell_type"] == "code"


#---------------------------------------------------------------------------------------------------
# DELIMITER CELLS
#---------------------------------------------------------------------------------------------------

def is_delim_cell(cell, delim, begin):
    """
    Returns whether a cell is a delimiter cell. Uses a regex in ``BEGIN_REGEXES`` or ``END_REGEXES`` 
    (based on the value of ``begin``). ``delim`` should be a key of one of these dictionaries.

    Args:
        cell (``nbformat.NotebookNode``): the cell in question
        delim (``str``): the delimiter type; a key of one of the regex dicts
        begin (``bool``): whether to look in ``BEGIN_REGEXES`` (rather than ``END REGEXES``)

    Returns:
        ``bool``: whether the cell is a delimiter cell
    """
    if not is_raw_cell(cell):
        return False
    source = get_source(cell)
    if begin:
        return bool(re.match(BEGIN_REGEXES[delim], source[0], flags=re.IGNORECASE))
    return bool(re.match(END_REGEXES[delim], source[0], flags=re.IGNORECASE))

def get_delim_config(cell, delim):
    """
    Returns the delimiter config given by running the source of ``cell`` through a YAML parser after
    removing the first line (the ``BEGIN __________`` line)

    Args:
        cell (``nbformat.NotebookNode``): the cell in question
        delim (``str``): the delimiter type; a key of ``BEGIN_REGEXES``
    
    Returns:
        iterable: the YAML-parsed config
    """
    assert is_raw_cell(cell), "cannot get delim config from non-raw cell"
    source = get_source(cell)[1:]
    config = yaml.full_load("\n".join(source))
    if config is None:
        return {}
    return config


#---------------------------------------------------------------------------------------------------
# AUTOGRADER CONFIG GENERATORS
#---------------------------------------------------------------------------------------------------

def gen_otter_file(notebook_path):
    """
    Uses ``Exam.config`` to generate a .otter file to configure student use of Otter tools, 
    including saving environments and submission to an Otter Service deployment

    Args:
        notebook_path (``pathlib.Path``): path to notebook
    """
    config = {}

    service = Exam.config.get('service', {})
    if service:
        config.update({
            "endpoint": service["endpoint"],
            "auth": service.get("auth", "google"),
            "assignment_id": service["assignment_id"],
            "class_id": service["class_id"]
        })

    config["notebook"] = service.get('notebook', notebook_path.name)
    config["save_environment"] = Exam.config.get("save_environment", False)
    config["ignore_modules"] = Exam.config.get("ignore_modules", [])

    if Exam.config.get("variables", None):
        config["variables"] = Exam.config.get("variables")

    config_path = notebook_path.with_suffix('.otter')
    with open(config_path, "w+") as f:
        json.dump(config, f, indent=4)

def gen_dot_ok(notebook_path, endpoint):
    """
    Generates .ok file and return its name
    
    Args:
        notebook_path (``pathlib.Path``): the path to the notebook
        endpoint (``str``): an endpoint specification for https://okpy.org
    
    Returns:
        ``str``: the name of the .ok file
    """
    assert notebook_path.suffix == '.ipynb', notebook_path
    ok_path = notebook_path.with_suffix('.ok')
    name = notebook_path.stem
    src = [notebook_path.name]
    with open(ok_path, 'w') as out:
        json.dump({
            "name": name,
            "endpoint": endpoint,
            "src": src,
            "tests": {
                "tests/q*.py": "ok_test"
            },
            "protocols": [
                "file_contents",
                "grading",
                "backup"
            ]
            }, out)
    return ok_path.name


#---------------------------------------------------------------------------------------------------
# MISCELLANEOUS CELL GENERATORS
#---------------------------------------------------------------------------------------------------

def gen_init_cell(dot_ok_name):
    """
    Generates a cell to initialize Otter or OkPy in the notebook. Uses ``Exam.otter()`` and ``Exam.ok()``
    to determine which type of init cell should be generated.

    Args:
        dot_ok_name (``str`` or ``None``): the name of the .ok file if it exists otherwise ``None``
    
    Returns:
        cell (``nbformat.NotebookNode``): new code cell
    """
    if Exam.otter():
        cell = nbformat.v4.new_code_cell("# Initialize Otter\nimport otter\ngrader = otter.Notebook()")
    elif Exam.ok():
        cell = nbformat.v4.new_code_cell(
            "# Initialize OK\nfrom client.api.notebook import Notebook\n"
            f"ok = Notebook(\"{dot_ok_name}\")")
    lock(cell)
    return cell

def gen_check_all_cell():
    """
    Generates a check-all cell that runs all tests for a notebook. Determines the format of this cell 
    using ``Exam.otter()`` and ``Exam.ok()``.
    
    Returns:
        ``list`` of ``nbformat.NotebookNode``: generated check-all cells
    """
    instructions = nbformat.v4.new_markdown_cell()
    instructions.source = "To double-check your work, the cell below will rerun all of the autograder tests."

    if Exam.otter():
        check_all = nbformat.v4.new_code_cell("grader.check_all()")
    elif Exam.ok():
        check_all = nbformat.v4.new_code_cell(dedent("""\
        # For your convenience, you can run this cell to run all the tests at once!
        import os
        print("Running all tests...")
        _ = [ok.grade(q[:-3]) for q in os.listdir("tests") if q.startswith('q') and len(q) <= 10]
        print("Finished running all tests.")    
        """))

    lock(instructions)
    lock(check_all)

    return [instructions, check_all]

def gen_export_cells(instruction_text, pdf=True, filtering=True):
    """
    Generates export or submit cells for the notebook. Determines the format of this cell using 
    ``Exam.otter()`` and ``Exam.ok()``.
    
    Args:
        instruction_text (``str``): extra instructions for students when exporting/submitting
        pdf (``bool``, optional): whether a PDF is needed; for Otter only
        filtering (``bool``, optional): whether PDF filtering is needed; for Otter only
    
    Returns:
        ``list`` of ``nbformat.NotebookNode``: generated export/submit cells

    """
    if Exam.otter():
        instructions = nbformat.v4.new_markdown_cell()
        instructions.source = "## Submission\n\nMake sure you have run all cells in your notebook in order before \
        running the cell below, so that all images/graphs appear in the output. The cell below will generate \
        a zipfile for you to submit. **Please save before exporting!**"
        
        if instruction_text:
            instructions.source += '\n\n' + instruction_text

        export = nbformat.v4.new_code_cell()
        source_lines = ["# Save your notebook first, then run this cell to export your submission."]
        if filtering and pdf:
            source_lines.append(f"grader.export()")
        elif not filtering:
            source_lines.append(f"grader.export(filtering=False)")
        else:
            source_lines.append(f"grader.export(pdf=False)")
        export.source = "\n".join(source_lines)

    elif Exam.ok():
        instructions = nbformat.v4.new_markdown_cell()
        instructions.source = (
            "## Submission\n\nOnce you're finished, select \"Save and Checkpoint\" " 
            "in the File menu and then execute the submit cell below. The result will contain a "
            "link that you can use to check that your assignment has been submitted successfully."
        )
        
        if instruction_text:
            instructions.source += '\n\n' + instruction_text

        export = nbformat.v4.new_code_cell()
        source_lines = ["# Save your notebook first, then run this cell to submit."]
        source_lines.append(f"_ = ok.submit()")
        export.source = "\n".join(source_lines)

    lock(instructions)
    lock(export)

    return [instructions, export, nbformat.v4.new_markdown_cell(" ")]    # last cell is buffer

def gen_question_header_cell(question_number):
    """
    Generates a Markdown cell with contents ``### Question {{ question_number }}`` to delimit questions
    in the exam.

    Args:
        question_number (``int``): the number of the question
    
    Returns:
        ``nbformat.NotebookNode``: the Markdown cell
    """
    return nbformat.v4.new_markdown_cell(f"### Question {question_number}")

def gen_version_header_cell(version_number):
    """
    Generates a Markdown cell with contents ``### Version {{ version_number }}`` to delimit versions
    in the exam noteook with solutions.

    Args:
        version_number (``int``): the number of the version
    
    Returns:
        ``nbformat.NotebookNode``: the Markdown cell
    """
    return nbformat.v4.new_markdown_cell(f"#### Version {version_number}")


#---------------------------------------------------------------------------------------------------
# TEST CELLS
#---------------------------------------------------------------------------------------------------

def is_test_cell(cell):
    """Returns whether a cell is a test cell
    
    Args:
        cell (``nbformat.NotebookNode``): a notebook cell

    Returns:
        ``bool``: whether the cell is a test cell
    """
    if cell['cell_type'] != 'code':
        return False
    source = get_source(cell)
    return source and re.match(TEST_REGEX, source[0], flags=re.IGNORECASE)

Test = namedtuple('Test', ['input', 'output', 'hidden'])

def read_test(cell):
    """Returns the contents of a test as an ``(input, output, hidden)`` named tuple
    
    Args:
        cell (``nbformat.NotebookNode``): a test cell

    Returns:
        ``Test``: test named tuple
    """
    hidden = bool(re.search("hidden", get_source(cell)[0], flags=re.IGNORECASE))
    output = ''
    for o in cell['outputs']:
        output += ''.join(o.get('text', ''))
        results = o.get('data', {}).get('text/plain')
        if results and isinstance(results, list):
            output += results[0]
        elif results:
            output += results
    return Test('\n'.join(get_source(cell)[1:]), output, hidden)

def write_test(path, test):
    """Writes an OK-formatted test file
    
    Args:
        path (``str``): path of file to be written
        test (``dict``): OK test to be written
    """
    with open(path, 'w') as f:
        f.write('test = ')
        pprint.pprint(test, f, indent=4, width=200, depth=None)

def gen_test_cell(name, points, tests, tests_dir):
    """
    Writes test files to tests directory. Returns a code cell that runs the check in either Otter
    or OkPy format.
    
    Args:
        name (``str``): the name of the test
        points (``int``): the value of the test
        tests (``list`` of ``Test``): tests to be written
        tests_dir (``pathlib.Path``): path to tests directory

    Returns:
        ``nbformat.NotebookNode``: code cell that runs the test
    """
    cell = nbformat.v4.new_code_cell()
    if Exam.otter():
        cell.source = ['grader.check("{}")'.format(name)]
    elif Exam.ok():
        cell.source = ['ok.grade("{}");'.format(name)]
    suites = [gen_suite(tests)]
    points = points
    
    test = {
        'name': name,
        'points': points,
        'suites': suites,
    }

    write_test(tests_dir / (name + '.py'), test)
    lock(cell)
    return cell

def gen_suite(tests):
    """Generates an OK test suite for a test
    
    Args:
        tests (``list`` of ``Test``): test cases

    Returns:
        ``dict``: OK test suite
    """
    cases = [gen_case(test) for test in tests]
    return  {
      'cases': cases,
      'scored': True,
      'setup': '',
      'teardown': '',
      'type': 'doctest'
    }

def gen_case(test):
    """Generates an OK test case for a test
    
    Args:
        test (``Test``): OK test for this test case

    Returns:
        ``dict``: the OK test case
    """
    code_lines = str_to_doctest(test.input.split('\n'), [])

    for i in range(len(code_lines) - 1):
        if code_lines[i+1].startswith('>>>') and len(code_lines[i].strip()) > 3 and not code_lines[i].strip().endswith("\\"):
            code_lines[i] += ';'

    code_lines.append(test.output)

    return {
        'code': '\n'.join(code_lines),
        'hidden': test.hidden,
        'locked': False
    }

def remove_hidden_tests(test_dir):
    """Rewrites test files to remove hidden tests
    
    Args:
        test_dir (``pathlib.Path``): path to test files directory
    """
    for f in test_dir.iterdir():
        if f.name == '__init__.py' or f.suffix != '.py':
            continue
        locals = {}
        with open(f) as f2:
            exec(f2.read(), globals(), locals)
        test = locals['test']
        for suite in test['suites']:
            for i, case in list(enumerate(suite['cases']))[::-1]:
                if case['hidden']:
                    suite['cases'].pop(i)
        write_test(f, test)

# def write_all_version_tests(output_dir):
#     for question in Exam.questions:
#         if not question.manual:
#             for version in question.versions:
#                 gen_test_cell(
#                     version.get_hash(),
#                     question.points,
#                     version.tests,
#                     output_dir
#                 )


#---------------------------------------------------------------------------------------------------
# SOLUTIONS
#---------------------------------------------------------------------------------------------------

def is_markdown_solution_cell(cell):
    """Returns whether a cell is a Markdown solution cell
    
    Args:
        cell (``nbformat.NotebookNode``): a notebook cell
    
    Returns:
        ``bool``: whether the cell is a Markdown solution cell
    """
    if not is_markdown_cell(cell):
        return False
    source = get_source(cell)
    return any([re.match(MD_SOLUTION_REGEX, l, flags=re.IGNORECASE) for l in source])

solution_assignment_re = re.compile('(\\s*[a-zA-Z0-9_ ]*=)(.*) #[ ]?SOLUTION')
def solution_assignment_sub(match):
    prefix = match.group(1)
    return prefix + ' ...'

solution_line_re = re.compile('(\\s*)([^#\n]+) #[ ]?SOLUTION')
def solution_line_sub(match):
    prefix = match.group(1)
    return prefix + '...'

begin_solution_re = re.compile(r'(\s*)# BEGIN SOLUTION( NO PROMPT)?')
skip_suffixes = ['# SOLUTION NO PROMPT', '# BEGIN PROMPT', '# END PROMPT']

SUBSTITUTIONS = [
    (solution_assignment_re, solution_assignment_sub),
    (solution_line_re, solution_line_sub),
]

def replace_solutions(lines):
    """Replaces solutions in lines, a list of strings
    
    Args:
        lines (``list`` of ``str``): solutions as a list of strings

    Returns:
        ``list`` of ``str``: stripped version of lines without solutions
    """
    stripped = []
    solution = False
    for line in lines:
        if any(line.endswith(s) for s in skip_suffixes):
            continue
        if solution and not line.endswith('# END SOLUTION'):
            continue
        if line.endswith('# END SOLUTION'):
            assert solution, 'END SOLUTION without BEGIN SOLUTION in ' + str(lines)
            solution = False
            continue
        begin_solution = begin_solution_re.match(line)
        if begin_solution:
            assert not solution, 'Nested BEGIN SOLUTION in ' + str(lines)
            solution = True
            if not begin_solution.group(2):
                line = begin_solution.group(1) + '...'
            else:
                continue
        for exp, sub in SUBSTITUTIONS:
            m = exp.match(line)
            if m:
                line = sub(m)
        stripped.append(line)
    assert not solution, 'BEGIN SOLUTION without END SOLUTION in ' + str(lines)
    return stripped

def replace_cell_solutions(cell):
    """
    Takes an arbitrary cell and replaces the solutions in it, if present. If a Markdown solution cell,
    replaces the entire cell with a Markdown response cell (copied from ``MARKDOWN_ANSWER_CELL_TEMPLATE```).
    If a code cell, replaces only lines that contain solution delimiting comments based on ``replace_solutions``.
    Otherwise, returns the original cell.

    Args:
        cell (``nbformat.NotebookNode``): the cell to replace
    
    Returns:
        ``nbformat.NotebookNode``: the sanitized cell
    """
    if is_markdown_solution_cell(cell):
        return copy.deepcopy(MARKDOWN_ANSWER_CELL_TEMPLATE)
    elif is_code_cell(cell):
        source = get_source(cell)
        stripped_source = replace_solutions(source)
        new_cell = copy.deepcopy(cell)
        new_cell.source = "\n".join(stripped_source)
        return new_cell
    else:
        return copy.deepcopy(cell)


#---------------------------------------------------------------------------------------------------
# NOTEBOOK PARSER
#---------------------------------------------------------------------------------------------------

def parse_notebook(nb):
    """
    Parses a master notebook into the requisite types and configurations needed for generating the exam.
    Populates fields in ``Exam`` and creates ``Questions`` and ``Versions`` based on delimeter cells.
    Raises ``AssertionError``s if the notebook is improperly formatted.

    Args:
        nb (``nbformat.NotebookNode``): the master notebook
    
    Raises:
        ``AssertionError``: if the notebook is improperly formatted (if ``BEGIN`` blocks have no ``END``
            if there are ``END`` blocks with no ``BEGIN``, or if there are cells outside a delimiter
            block)
    """
    in_introduction, in_question, in_version, in_conclusion = tuple(False for _ in range(4))
    cells, config = [], {}
    questions, versions = [], []
    for cell in nb.cells:

        # check for BEGIN cells and parse configs (if applicable)
        if is_delim_cell(cell, "exam", True):
            Exam.config = get_delim_config(cell, "exam")
        elif is_delim_cell(cell, "introduction", True):
            assert all([not in_introduction, not in_question, not in_version, not in_conclusion]), \
                f"BEGIN INTRODUCTION detected inside another block"
            in_introduction = True
        elif is_delim_cell(cell, "question", True):
            assert all([not in_introduction, not in_question, not in_version, not in_conclusion]), \
                f"BEGIN QUESTION detected inside another block"
            in_question = True
            config = get_delim_config(cell, "question")
        elif is_delim_cell(cell, "version", True):
            assert all([not in_introduction, in_question, not in_version, not in_conclusion]), \
                f"BEGIN VERSION detected inside an incompatible block or outside a question block"
            in_version = True
        elif is_delim_cell(cell, "conclusion", True):
            assert all([not in_introduction, not in_question, not in_version, not in_conclusion]), \
                f"BEGIN CONCLUSION detected inside another block"
            in_conclusion = True
        
        # check for END cells and update vars
        elif in_introduction and is_delim_cell(cell, "introduction", False):
            in_introduction = False
            Exam.introduction = copy.deepcopy(cells)
            cells = []
        elif in_question and is_delim_cell(cell, "question", False):
            in_question = False
            # handle case when there is only 1 version and no BEGIN/END VERSION provided
            if len(versions) == 0 and len(cells) > 0:
                versions = [Version(copy.deepcopy(cells))]
                cells = []
            questions.append(Question(versions, config.get("points", 1), config.get("manual", False)))
            versions, config, cells = [], {}, []
        elif in_version and is_delim_cell(cell, "version", False):
            in_version = False
            versions.append(Version(copy.deepcopy(cells)))
            cells = []
        elif in_conclusion and is_delim_cell(cell, "conclusion", False):
            in_conclusion = False
            Exam.conclusion = copy.deepcopy(cells)
            cells = []
        
        # raise errors for ENDs or other cells outside their blocks
        elif is_delim_cell(cell, "introduction", False):
            raise AssertionError("END INTRODUCTION found outside introduction block")
        elif is_delim_cell(cell, "question", False):
            raise AssertionError("END QUESTION found outside question block")
        elif is_delim_cell(cell, "version", False):
            raise AssertionError("END VERSION found outside version block")
        elif is_delim_cell(cell, "conclusion", False):
            raise AssertionError("END CONCLUSION found outside conclusion block")

        # collect cells that are in between delim cells
        elif in_introduction or in_question or in_version or in_conclusion:
            cells.append(cell)

        else:
            raise AssertionError(f"Cell found outside a block: {cell}")
    
        # put the questions into Exam
        Exam.questions = questions


#---------------------------------------------------------------------------------------------------
# MAIN METHOD
#---------------------------------------------------------------------------------------------------

def main(args):
    """
    Runs jExam. Parses master notebook, seeds ``np.random``, and creates the number of exams specified
    in the exam config. Writes these to ``{{ args.result }}/exam_*``. Also writes a solutions notebook
    containing all questions, versions, and autograder tests to ``{{ args.result }}/autograder``. If
    specified, also generates a Gradescope zip file to use with Otter.

    Args:
        args (``argparse.Namespace``): parsed command-line arguments

    Raises:
        ``AssertionError``: if ``args.format`` is invalid
    """
    master, result = pathlib.Path(args.master), pathlib.Path(args.result)

    # update Exam.autograder_format
    assert args.format in ["otter", "ok"], f"Autograder format {args.format} invalid"
    Exam.autograder_format = args.format

    # load notebook and parse
    nb = nbformat.read(master, as_version=NB_VERSION)
    parse_notebook(nb)

    # seed np.random in advance of creating student versions
    seed = args.seed or Exam.config.get("seed", 42)
    np.random.seed(seed)

    # create autograder notebook
    nb_name = master.name
    create_and_write_autograder_exam(result / "autograder", nb_name)

    # create exams
    for i in range(Exam.config["num_students"]):
        if (i + 1) % 50 == 0 and not args.quiet:
            print(f"Generating exam {i + 1}")
        output_dir = result / f"exam_{i}"
        create_and_write_exam_instance(output_dir, nb_name, Exam.config["num_questions"])

    # all_tests_path = result / 'tests'
    # os.makedirs(all_tests_path, exist_ok=True)
    # write_all_version_tests(all_tests_path)

    # generate Gradescope zip file
    if Exam.config.get("generate", {}):
        if not args.quiet:
            print("Generating autograder zip file...")
            generate(args.result, Exam.config.get("generate"))
