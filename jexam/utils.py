###########################
##### jExam Utilities #####
###########################

def str_to_doctest(code_lines, lines):
    """
    Converts a list of lines of Python code ``code_lines`` to a list of doctest-formatted lines ``lines``

    Args:
        code_lines (``list``): list of lines of python code
        lines (``list``): set of characters used to create function name
    
    Returns:
        ``list`` of ``str``: doctest formatted list of lines
    """
    if len(code_lines) == 0:
        return lines
    line = code_lines.pop(0)
    if line.startswith(" ") or line.startswith("\t"):
        return str_to_doctest(code_lines, lines + ["... " + line])
    elif line.startswith("except:") or line.startswith("elif ") or line.startswith("else:") or line.startswith("finally:"):
        return str_to_doctest(code_lines, lines + ["... " + line])
    elif len(lines) > 0 and lines[-1].strip().endswith("\\"):
        return str_to_doctest(code_lines, lines + ["... " + line])
    else:
        return str_to_doctest(code_lines, lines + [">>> " + line])

def generate(result, config):
    try:
        from otter.argparser import get_parser
        parser = get_parser()
    except ImportError:
        raise ImportError("You must have otter-grader installed to generate a Gradescope zip file.")
    
    curr_dir = os.getcwd()
    os.chdir(result)
    generate_cmd = ["generate", "autograder"]

    if config.get('points', None) is not None:
        generate_cmd += ["--points", config.get('points', None)]
    
    if config.get('threshold', None) is not None:
        generate_cmd += ["--threshold", config.get('threshold', None)]
    
    if config.get('show_stdout', False):
        generate_cmd += ["--show-stdout"]
    
    if config.get('show_hidden', False):
        generate_cmd += ["--show-hidden"]
    
    if config.get('grade_from_log', False):
        generate_cmd += ["--grade-from-log"]
    
    if config.get('seed', None) is not None:
        generate_cmd += ["--seed", str(config.get('seed', None))]

    if config.get('pdfs', {}):
        pdf_args = config.get('pdfs', {})
        token = APIClient.get_token()
        generate_cmd += ["--token", token]
        generate_cmd += ["--course-id", str(pdf_args["course_id"])]
        generate_cmd += ["--assignment-id", str(pdf_args["assignment_id"])]

        if not pdf_args.get("filtering", True):
            generate_cmd += ["--unfiltered-pdfs"]
    
    if config.get('files', []):
        generate_cmd += config.get('files', [])

    if config.get('variables', {}):
        generate_cmd += ["--serialized-variables", str(config["variables"])]
    
    args = parser.parse_args(generate_cmd)
    args.func(args)

    os.chdir(curr_dir)
