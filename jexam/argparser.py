#################################
##### jExam Argument Parser #####
#################################

import argparse

from .distribute import main as distribute
from .generate import main as generate

def get_parser():
    """
    Creates and returns the argument parser for jExam
    
    Returns:
        ``argparse.ArgumentParser``: the argument parser for jExam
    """
    parser = argparse.ArgumentParser()

    generate_parser = parser.add_subparsers("generate")
    generate_parser.add_argument("master", type=str, help="Path to exam master notebook")
    generate_parser.add_argument("result", nargs="?", default="dist", help="Path at which to write output notebooks")
    generate_parser.add_argument("-f", "--format", type=str, default="otter", help="Name of autograder format; 'otter' or 'ok'")
    generate_parser.add_argument("-s", "--seed", type=int, default=None, help="Random seed for NumPy to run before execution")
    generate_parser.add_argument("-q", "--quiet", default=False, action="store_true", help="Run without printing status")
    generate_parser.set_defaults(func=generate)

    distribute_parser = parser.add_subparsers("distribute")
    distribute_parser.set_defaults(func=distribute)

    return parser
